"""Claim models — mirror fact_claims.csv and fact_claim_lines.csv."""

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal, TypeVar

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints, model_validator

from app.models.common import (
    ClaimId,
    CptCode,
    DepartmentId,
    DomainModel,
    FacilityId,
    Icd10Code,
    LineId,
    Money,
    OptionalStr,
    PatientId,
    PayerId,
    ProviderId,
)
from app.models.common import _blank_to_none
from app.models.denial import Denial
from app.models.patient import Patient
from app.models.payer import Payer
from app.models.provider import Provider

T = TypeVar("T")


def _split_pipe(value: object) -> object:
    """Multi-value columns are stored as "A|B" strings in the claims frame."""
    if isinstance(value, str):
        return [part for part in value.split("|") if part]
    return value


PipeList = Annotated[list[T], BeforeValidator(_split_pipe)]


class ClaimStatus(StrEnum):
    DRAFT = "Draft"  # entered and validated, not yet sent to the payer
    PENDING = "Pending"  # submitted, awaiting the payer's decision
    PAID = "Paid"
    DENIED = "Denied"


# The payer has decided these; denial and collection rates count only them
ADJUDICATED_STATUSES = (ClaimStatus.PAID, ClaimStatus.DENIED)


class ClaimType(StrEnum):
    PROFESSIONAL = "Professional"  # CMS-1500 / 837P
    INSTITUTIONAL = "Institutional"  # UB-04 / 837I


class PlaceOfService(StrEnum):
    OFFICE = "11"
    OUTPATIENT_HOSPITAL = "22"
    EMERGENCY_ROOM = "23"


class ClaimLine(DomainModel):
    line_id: LineId
    claim_id: ClaimId
    line_number: int = Field(ge=1)
    cpt_code: CptCode
    cpt_category: str
    modifier: OptionalStr = None
    units: int = Field(ge=1)
    charge_amount: Money
    allowed_amount: Money
    paid_amount: Money
    icd10_pointer: Icd10Code


class Claim(DomainModel):
    """Claim header — one row of fact_claims.csv. Used in list responses."""

    claim_id: ClaimId
    patient_id: PatientId
    provider_id: ProviderId
    payer_id: PayerId
    facility_id: FacilityId
    department_id: DepartmentId
    service_date: date
    submission_date: date
    total_charge: Money
    total_allowed: Money
    total_paid: Money
    patient_responsibility: Money
    status: ClaimStatus
    claim_type: ClaimType
    place_of_service: PlaceOfService
    primary_icd10: Icd10Code
    days_in_ar: int = Field(ge=0)
    is_clean_claim: bool
    pa_required: bool
    pa_obtained: bool
    pa_number: OptionalStr = None
    has_corrections: bool = Field(
        default=False, description="True if AI Fix corrections are layered over the source data"
    )
    is_overdue: bool = Field(
        default=False, description="Pending longer than the payer's average days to pay"
    )
    additional_icd10: PipeList[Icd10Code] = Field(
        default_factory=list, description="Diagnoses after the primary, in order"
    )
    other_payer_ids: PipeList[PayerId] = Field(
        default_factory=list, description="Secondary and tertiary coverage, in order"
    )

    @model_validator(mode="after")
    def _check_dates(self) -> "Claim":
        _check_submission_date(self.service_date, self.submission_date)
        return self

    @property
    def missing_prior_auth(self) -> bool:
        return self.pa_required and not self.pa_obtained


def _check_submission_date(service_date: date, submission_date: date) -> None:
    if submission_date < service_date:
        raise ValueError("submission_date cannot precede service_date")


# A claim form (CMS-1500 / UB-04) carries up to 12 diagnoses
MAX_DIAGNOSES = 12
MAX_OTHER_PAYERS = 2  # secondary and tertiary coverage

Modifier = Annotated[str, StringConstraints(pattern=r"^[A-Z0-9]{2}$")]


class ClaimLineCreate(DomainModel):
    """One service rendered. The charge defaults to the CPT's standard charge × units."""

    cpt_code: CptCode
    units: int = Field(default=1, ge=1, le=99)
    modifier: Annotated[Modifier | None, BeforeValidator(_blank_to_none)] = None
    charge_amount: Money | None = None
    icd10_pointer: Icd10Code = Field(description="The diagnosis this service treats")


class ClaimCreate(DomainModel):
    """A manually entered claim for a registered patient. It starts as a Draft.

    `diagnoses[0]` is the primary diagnosis. Every diagnosis must be supported by at
    least one service line, and every line must point at a listed diagnosis. The
    department follows from the provider. `submission_date` is the planned date until
    the claim is marked submitted.
    """

    patient_id: PatientId
    payer_id: PayerId = Field(description="The payer billed by this claim")
    other_payer_ids: list[PayerId] = Field(
        default_factory=list,
        max_length=MAX_OTHER_PAYERS,
        description="Additional coverage, in order: secondary, then tertiary",
    )
    provider_id: ProviderId
    facility_id: FacilityId = "FAC001"
    diagnoses: list[Icd10Code] = Field(min_length=1, max_length=MAX_DIAGNOSES)
    lines: list[ClaimLineCreate] = Field(min_length=1, max_length=50)
    claim_type: ClaimType
    place_of_service: PlaceOfService = PlaceOfService.OFFICE
    service_date: date
    submission_date: date
    pa_required: bool = False
    pa_obtained: bool = False
    pa_number: OptionalStr = None

    @model_validator(mode="after")
    def _check_fields(self) -> "ClaimCreate":
        _check_submission_date(self.service_date, self.submission_date)
        if self.pa_obtained and not self.pa_required:
            raise ValueError("pa_obtained requires pa_required")
        if self.pa_number and not self.pa_obtained:
            raise ValueError("pa_number requires pa_obtained")

        if len(set(self.diagnoses)) != len(self.diagnoses):
            raise ValueError("Each diagnosis can only be listed once")
        payers = [self.payer_id, *self.other_payer_ids]
        if len(set(payers)) != len(payers):
            raise ValueError("Each payer can only be listed once")

        listed = set(self.diagnoses)
        for number, line in enumerate(self.lines, start=1):
            if line.icd10_pointer not in listed:
                raise ValueError(
                    f"Line {number} points at {line.icd10_pointer}, which isn't a listed diagnosis"
                )
        treated = {line.icd10_pointer for line in self.lines}
        unsupported = [code for code in self.diagnoses if code not in treated]
        if unsupported:
            raise ValueError(
                f"Every diagnosis needs a service line: add one for {', '.join(unsupported)}"
            )
        return self


ClaimSortField = Literal[
    "claim_id", "service_date", "submission_date", "total_charge", "total_paid", "days_in_ar"
]


class ClaimQuery(BaseModel):
    """Search, filter, sort, and pagination parameters for listing claims."""

    search: str | None = Field(
        default=None, description="Substring match on claim_id, patient_id, or primary_icd10"
    )
    payer_id: PayerId | None = None
    provider_id: ProviderId | None = None
    department_id: DepartmentId | None = None
    status: ClaimStatus | None = None
    claim_type: ClaimType | None = None
    is_clean_claim: bool | None = None
    missing_prior_auth: bool | None = None
    overdue: bool | None = None
    service_date_from: date | None = None
    service_date_to: date | None = None
    min_charge: Money | None = None
    max_charge: Money | None = None
    sort_by: ClaimSortField = "service_date"
    sort_desc: bool = True
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=200)


class ClaimDetail(Claim):
    """Claim with its lines, denials, and resolved patient/payer/provider. Used by /api/claims/{id}."""

    lines: list[ClaimLine] = Field(default_factory=list)
    denials: list[Denial] = Field(default_factory=list)
    patient: Patient | None = None
    payer: Payer | None = None
    provider: Provider | None = None
