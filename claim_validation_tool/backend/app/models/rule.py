"""Validation rule models, the catalog of claim fields rules can test, and validation results."""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    Field,
    StringConstraints,
    computed_field,
    model_validator,
)

from app.models.claim import ClaimDetail, ClaimType, ClaimStatus, PlaceOfService
from app.models.common import ClaimId, DomainModel

RuleId = Annotated[str, StringConstraints(pattern=r"^RULE-\d{3,}$")]


class Severity(StrEnum):
    ERROR = "error"  # blocks the claim
    WARNING = "warning"  # flags for review
    INFO = "info"


class RuleCategory(StrEnum):
    CODING = "Coding"
    ELIGIBILITY = "Eligibility"
    AUTHORIZATION = "Authorization"
    DEMOGRAPHICS = "Demographics"
    BILLING = "Billing"
    REQUIRED_FIELDS = "Required Fields"
    PAYER_SPECIFIC = "Payer-Specific"


class Operator(StrEnum):
    IS_EMPTY = "isEmpty"
    IS_NOT_EMPTY = "isNotEmpty"
    EQUALS = "equals"
    NOT_EQUALS = "notEquals"
    GREATER_THAN = "greaterThan"
    LESS_THAN = "lessThan"
    CONTAINS = "contains"


class ConditionLogic(StrEnum):
    AND = "AND"
    OR = "OR"


class FieldType(StrEnum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    ENUM = "enum"


class RuleField(BaseModel):
    """A claim field that rule conditions can test. Served to the rule builder UI."""

    field: str
    label: str
    type: FieldType
    options: list[str] | None = None

    @computed_field
    @property
    def operators(self) -> list[Operator]:
        """Operators valid for this field, in display order."""
        return [op for op in Operator if op in _OPERATORS_BY_TYPE[self.type]]


def _enum_field(field: str, label: str, enum: type[StrEnum]) -> RuleField:
    return RuleField(field=field, label=label, type=FieldType.ENUM, options=[e.value for e in enum])


RULE_FIELDS: dict[str, RuleField] = {
    f.field: f
    for f in [
        RuleField(field="claim_id", label="Claim ID", type=FieldType.STRING),
        RuleField(field="patient_id", label="Patient ID", type=FieldType.STRING),
        RuleField(field="provider_id", label="Provider ID", type=FieldType.STRING),
        RuleField(field="payer_id", label="Payer ID", type=FieldType.STRING),
        RuleField(field="facility_id", label="Facility ID", type=FieldType.STRING),
        RuleField(field="department_id", label="Department ID", type=FieldType.STRING),
        RuleField(field="service_date", label="Service Date", type=FieldType.DATE),
        RuleField(field="submission_date", label="Submission Date", type=FieldType.DATE),
        RuleField(field="days_to_submission", label="Days to Submission", type=FieldType.NUMBER),
        RuleField(field="total_charge", label="Total Charge", type=FieldType.NUMBER),
        RuleField(field="total_allowed", label="Total Allowed", type=FieldType.NUMBER),
        RuleField(field="total_paid", label="Total Paid", type=FieldType.NUMBER),
        RuleField(
            field="patient_responsibility", label="Patient Responsibility", type=FieldType.NUMBER
        ),
        _enum_field("status", "Claim Status", ClaimStatus),
        _enum_field("claim_type", "Claim Type", ClaimType),
        _enum_field("place_of_service", "Place of Service", PlaceOfService),
        RuleField(field="primary_icd10", label="Primary ICD-10", type=FieldType.STRING),
        RuleField(field="days_in_ar", label="Days in AR", type=FieldType.NUMBER),
        RuleField(field="is_clean_claim", label="Clean Claim", type=FieldType.BOOLEAN),
        RuleField(field="pa_required", label="Prior Auth Required", type=FieldType.BOOLEAN),
        RuleField(field="pa_obtained", label="Prior Auth Obtained", type=FieldType.BOOLEAN),
        RuleField(field="pa_number", label="Prior Auth Number", type=FieldType.STRING),
        RuleField(field="is_overdue", label="Overdue (pending)", type=FieldType.BOOLEAN),
        RuleField(
            field="payer_is_patient_primary",
            label="Billed to Patient's Primary Payer",
            type=FieldType.BOOLEAN,
        ),
        RuleField(
            field="patient_primary_on_claim",
            label="Patient's Primary Payer on Claim",
            type=FieldType.BOOLEAN,
        ),
    ]
}

# Which operators make sense for each field type
_OPERATORS_BY_TYPE: dict[FieldType, set[Operator]] = {
    FieldType.STRING: {
        Operator.IS_EMPTY,
        Operator.IS_NOT_EMPTY,
        Operator.EQUALS,
        Operator.NOT_EQUALS,
        Operator.CONTAINS,
    },
    FieldType.ENUM: {Operator.EQUALS, Operator.NOT_EQUALS},
    FieldType.BOOLEAN: {Operator.EQUALS, Operator.NOT_EQUALS},
    FieldType.NUMBER: {
        Operator.EQUALS,
        Operator.NOT_EQUALS,
        Operator.GREATER_THAN,
        Operator.LESS_THAN,
    },
    FieldType.DATE: {
        Operator.EQUALS,
        Operator.NOT_EQUALS,
        Operator.GREATER_THAN,
        Operator.LESS_THAN,
    },
}

_VALUELESS_OPERATORS = {Operator.IS_EMPTY, Operator.IS_NOT_EMPTY}


def _scalar_to_str(value: Any) -> Any:
    """Rule builder forms send strings, but accept JSON numbers/booleans too."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return value


def parse_condition_value(field: RuleField, raw: str) -> str | float | bool:
    """Convert a condition's string value to the field's type. Raises ValueError if invalid."""
    match field.type:
        case FieldType.NUMBER:
            try:
                return float(raw)
            except ValueError:
                raise ValueError(f"{field.field} expects a number, got {raw!r}") from None
        case FieldType.BOOLEAN:
            lowered = raw.strip().lower()
            if lowered not in {"true", "false"}:
                raise ValueError(f"{field.field} expects true or false, got {raw!r}")
            return lowered == "true"
        case FieldType.DATE:
            try:
                return date.fromisoformat(raw).isoformat()
            except ValueError:
                raise ValueError(f"{field.field} expects a YYYY-MM-DD date, got {raw!r}") from None
        case FieldType.ENUM:
            if raw not in (field.options or []):
                raise ValueError(f"{field.field} must be one of {field.options}, got {raw!r}")
            return raw
        case _:
            return raw


class Condition(BaseModel):
    field: str
    operator: Operator
    value: Annotated[str | None, BeforeValidator(_scalar_to_str)] = None

    @model_validator(mode="after")
    def _check(self) -> "Condition":
        spec = RULE_FIELDS.get(self.field)
        if spec is None:
            raise ValueError(f"Unknown field {self.field!r}; see GET /api/rules/fields")
        if self.operator not in _OPERATORS_BY_TYPE[spec.type]:
            raise ValueError(f"Operator {self.operator} is not valid for {spec.type} field {self.field}")
        if self.operator in _VALUELESS_OPERATORS:
            self.value = None
        elif self.value is None or not self.value.strip():
            raise ValueError(f"Operator {self.operator} requires a value")
        else:
            parse_condition_value(spec, self.value)
        return self


class ScopeType(StrEnum):
    ALL = "all"
    PAYER = "payer"
    CLAIM_TYPE = "claim_type"
    DEPARTMENT = "department"


# Claim column each scope type filters on
SCOPE_COLUMNS: dict[ScopeType, str] = {
    ScopeType.PAYER: "payer_id",
    ScopeType.CLAIM_TYPE: "claim_type",
    ScopeType.DEPARTMENT: "department_id",
}


class RuleScope(BaseModel):
    """Which claims a rule applies to. A claim is in scope if it matches any of `values`."""

    type: ScopeType = ScopeType.ALL
    values: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> "RuleScope":
        if self.type == ScopeType.ALL:
            self.values = []
        elif not self.values:
            raise ValueError(f"Scope {self.type} requires at least one value")
        return self


class RuleDefinition(BaseModel):
    """The part of a rule that decides which claims it flags. Used to test draft rules."""

    scope: RuleScope = Field(default_factory=RuleScope)
    conditions: list[Condition] = Field(min_length=1)
    condition_logic: ConditionLogic = ConditionLogic.AND


class RuleCreate(RuleDefinition):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    category: RuleCategory
    severity: Severity
    enabled: bool = True
    recommended_action: str = ""


class RuleUpdate(BaseModel):
    """Partial update: only the fields sent are changed."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    category: RuleCategory | None = None
    severity: Severity | None = None
    enabled: bool | None = None
    recommended_action: str | None = None
    scope: RuleScope | None = None
    conditions: list[Condition] | None = Field(default=None, min_length=1)
    condition_logic: ConditionLogic | None = None


class Rule(RuleCreate):
    id: RuleId
    created_at: datetime
    updated_at: datetime


# --- Results -------------------------------------------------------------------


class RuleTestResult(BaseModel):
    """How a draft rule would behave across the whole claims dataset."""

    total_claims: int
    in_scope: int
    matched: int
    sample_claim_ids: list[ClaimId] = Field(description="Up to 20 matching claims")


class ValidationStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    ERROR = "error"
    AI_FIX = "aifix"  # has errors and risk is high enough to warrant an AI-suggested fix


class RuleFinding(BaseModel):
    rule_id: RuleId
    rule_name: str
    severity: Severity
    category: RuleCategory
    message: str
    recommended_action: str


class RiskFactor(BaseModel):
    label: str
    points: int


class ClaimValidation(DomainModel):
    claim_id: ClaimId
    status: ValidationStatus
    risk_score: int = Field(ge=0, le=100)
    risk_factors: list[RiskFactor]
    findings: list[RuleFinding]


class ClaimCreated(BaseModel):
    """Response to POST /api/claims: the new claim and its validation result."""

    claim: ClaimDetail
    validation: ClaimValidation


class ValidateRequest(BaseModel):
    claim_ids: list[ClaimId] = Field(min_length=1, max_length=200)
    rule_ids: list[RuleId] | None = Field(
        default=None, description="Only run these rules (default: all enabled rules)"
    )
