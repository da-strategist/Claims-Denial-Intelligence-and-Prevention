"""Denial model — mirrors fact_denials.csv."""

from datetime import date
from enum import StrEnum

from pydantic import Field

from app.models.common import ClaimId, DenialId, DomainModel, Money, PayerId


class DenialCategory(StrEnum):
    CODING_ERRORS = "Coding Errors"
    PRIOR_AUTHORIZATION = "Prior Authorization"
    MISSING_INACCURATE_DATA = "Missing/Inaccurate Data"
    ELIGIBILITY = "Eligibility"
    MEDICAL_NECESSITY = "Medical Necessity"
    DUPLICATE = "Duplicate"
    TIMELY_FILING = "Timely Filing"


class WorkflowStep(StrEnum):
    """Revenue-cycle step where the failure that caused the denial occurred."""

    PATIENT_REGISTRATION = "patient_registration"
    ELIGIBILITY_VERIFICATION = "eligibility_verification"
    PRIOR_AUTHORIZATION = "prior_authorization"
    CLINICAL_SERVICE = "clinical_service"
    MEDICAL_CODING = "medical_coding"
    CLAIM_SCRUBBING = "claim_scrubbing"
    CLAIM_SUBMISSION = "claim_submission"


class Denial(DomainModel):
    denial_id: DenialId
    claim_id: ClaimId
    payer_id: PayerId
    denial_date: date
    root_cause_category: DenialCategory
    carc_code: str = Field(description="Claim Adjustment Reason Code")
    rarc_code: str = Field(description="Remittance Advice Remark Code")
    denial_amount: Money
    workflow_failure_point: WorkflowStep
    is_preventable: bool
    denial_reason_text: str
    days_to_denial: int = Field(ge=0)
