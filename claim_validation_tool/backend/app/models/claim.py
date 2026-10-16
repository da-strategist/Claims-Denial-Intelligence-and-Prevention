"""Claim models — mirror fact_claims.csv and fact_claim_lines.csv."""

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

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
from app.models.denial import Denial
from app.models.payer import Payer
from app.models.provider import Provider


class ClaimStatus(StrEnum):
    PAID = "Paid"
    DENIED = "Denied"


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

    @model_validator(mode="after")
    def _check_dates(self) -> "Claim":
        if self.submission_date < self.service_date:
            raise ValueError("submission_date cannot precede service_date")
        return self

    @property
    def missing_prior_auth(self) -> bool:
        return self.pa_required and not self.pa_obtained


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
    service_date_from: date | None = None
    service_date_to: date | None = None
    min_charge: Money | None = None
    max_charge: Money | None = None
    sort_by: ClaimSortField = "service_date"
    sort_desc: bool = True
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=200)


class ClaimDetail(Claim):
    """Claim with its lines, denials, and resolved payer/provider. Used by /api/claims/{id}."""

    lines: list[ClaimLine] = Field(default_factory=list)
    denials: list[Denial] = Field(default_factory=list)
    payer: Payer | None = None
    provider: Provider | None = None
