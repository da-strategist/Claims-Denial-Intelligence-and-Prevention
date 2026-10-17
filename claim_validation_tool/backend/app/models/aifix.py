"""AI Fix models: fix suggestions with citations, and corrections applied to claims."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, computed_field

from app.models.common import ClaimId
from app.models.rule import ClaimValidation, FieldType, RuleId


# Claim fields an applied fix may change. Everything else is read-only source data.
CORRECTABLE_FIELDS = ("primary_icd10", "pa_obtained", "pa_number", "is_clean_claim")


class SuggestionAction(StrEnum):
    APPLY = "apply"  # can be written to the claim (pre-filled or with specialist input)
    MANUAL = "manual"  # a task for the billing specialist outside the system
    CLARIFY = "clarify"  # ambiguous: needs research or judgement before acting


class ClarificationTopic(StrEnum):
    """What the clarification assistant researches for a suggestion. Ordered by priority."""

    MEDICAL_NECESSITY = "medical_necessity"
    NCCI_MODIFIERS = "ncci_modifiers"
    PAYER_PRIOR_AUTH = "payer_prior_auth"
    APPEAL = "appeal"


class Confidence(StrEnum):
    HIGH = "high"  # derived directly from the claim's own data
    MEDIUM = "medium"  # standard procedure that usually resolves the finding
    LOW = "low"  # needs clinical or payer-specific judgement


class SourceType(StrEnum):
    CARC = "carc"
    RARC = "rarc"
    PAYER = "payer"
    PAYER_CONTRACT = "payer_contract"
    ICD10 = "icd10"
    CLAIM_DATA = "claim_data"
    RULE = "rule"
    # Reference tables the clarification assistant also retrieves from
    NCCI_EDIT = "ncci_edit"
    MUE = "mue"
    COVERAGE_POLICY = "coverage_policy"  # LCD / NCD
    FEE_SCHEDULE = "fee_schedule"


class Citation(BaseModel):
    """Where a suggestion's facts come from, so the specialist can verify them."""

    source_type: SourceType
    reference_id: str
    title: str
    excerpt: str


class ProposedChange(BaseModel):
    """A claim field the fix would set. `suggested_value` is None when the specialist must supply it."""

    field: str
    label: str
    type: FieldType
    current_value: str | None
    suggested_value: str | None = None
    options: list[str] | None = Field(default=None, description="Known good values to choose from")

    @computed_field
    @property
    def requires_input(self) -> bool:
        return self.suggested_value is None


class FixSuggestion(BaseModel):
    id: str = Field(description="Stable per claim and finding, e.g. CLM0000002:RULE-002")
    claim_id: ClaimId
    rule_id: RuleId | None = Field(default=None, description="The finding this addresses, if any")
    title: str
    summary: str
    reasoning: str
    steps: list[str] = Field(default_factory=list)
    action: SuggestionAction
    confidence: Confidence
    changes: list[ProposedChange] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    clarification_topic: ClarificationTopic | None = None
    source: str = Field(default="rule_based", description="Which suggester produced this")

    @computed_field
    @property
    def needs_clarification(self) -> bool:
        return self.clarification_topic is not None


class Correction(BaseModel):
    """One field changed on a claim by applying a fix. Source claim data is never modified."""

    id: str
    claim_id: ClaimId
    field: str
    old_value: str | None
    new_value: str
    suggestion_id: str
    applied_at: datetime


class ClaimFixes(BaseModel):
    claim_id: ClaimId
    validation: ClaimValidation
    suggestions: list[FixSuggestion]
    corrections: list[Correction]


class ApplyFixRequest(BaseModel):
    suggestion_id: str
    values: dict[str, str] = Field(
        default_factory=dict,
        description="Values for the suggestion's changes, by field. Overrides suggested values.",
    )


class ApplyFixResult(BaseModel):
    claim_id: ClaimId
    applied: list[Correction]
    before: ClaimValidation
    after: ClaimFixes
