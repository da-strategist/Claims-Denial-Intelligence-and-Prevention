"""Saved drafts: New Claim forms saved part-way through, before they become claims.

A saved draft is not a claim. It isn't validated, scored, listed with claims, or counted on
the dashboard, so its fields may be incomplete or half-typed. They are still bounded (IDs
in their formats, short strings, the same list limits as ClaimCreate) so the store holds
claim forms and nothing else. Drafts are shared by everyone who can enter claims and
expire DRAFT_RETENTION_DAYS after they were last saved.
"""

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints

from app.models.billing import Relationship
from app.models.claim import MAX_DIAGNOSES, MAX_OTHER_PAYERS, ClaimType, PlaceOfService
from app.models.common import (
    DomainModel,
    FacilityId,
    PatientId,
    PayerId,
    ProviderId,
    _blank_to_none,
)
from app.models.patient import PatientSummary

DRAFT_RETENTION_DAYS = 30

DraftId = Annotated[str, StringConstraints(pattern=r"^DRF-[0-9a-f]{8}$")]


def _optional(type_):
    """An ID that may not be chosen yet: "" or missing becomes None."""
    return Annotated[type_ | None, BeforeValidator(_blank_to_none)]


# As typed: a diagnosis or CPT code may be half entered
Partial = Annotated[str, StringConstraints(max_length=12, strip_whitespace=True)]


class DraftLine(BaseModel):
    cpt_code: Partial = ""
    units: Annotated[str, StringConstraints(max_length=6)] = "1"
    modifier: Annotated[str, StringConstraints(max_length=4)] = ""
    charge: Annotated[str, StringConstraints(max_length=12)] = ""
    dx: int = Field(default=0, ge=0, lt=MAX_DIAGNOSES, description="Which diagnosis, by position")
    revenue_code: Annotated[str, StringConstraints(max_length=4)] = ""


Text = Annotated[str, StringConstraints(max_length=60)]


class DraftAddress(BaseModel):
    line1: Text = ""
    line2: Text = ""
    city: Text = ""
    state: Annotated[str, StringConstraints(max_length=2)] = ""
    zip_code: Annotated[str, StringConstraints(max_length=10)] = ""


class DraftPolicy(BaseModel):
    member_id: Annotated[str, StringConstraints(max_length=30)] = ""
    group_number: Annotated[str, StringConstraints(max_length=30)] = ""
    relationship: Relationship = Relationship.SELF
    first_name: Text = ""
    last_name: Text = ""
    birth_date: Annotated[str, StringConstraints(max_length=10)] = ""
    sex: Annotated[str, StringConstraints(max_length=1)] = ""


class DraftInstitutional(BaseModel):
    type_of_bill: Annotated[str, StringConstraints(max_length=3)] = ""
    admission_type: Annotated[str, StringConstraints(max_length=1)] = ""
    admission_source: Annotated[str, StringConstraints(max_length=1)] = ""
    patient_status: Annotated[str, StringConstraints(max_length=2)] = ""


class DraftBilling(BaseModel):
    """The form's billing fields as typed (dates as text, nothing required)."""

    patient_birth_date: Annotated[str, StringConstraints(max_length=10)] = ""
    patient_address: DraftAddress = Field(default_factory=DraftAddress)
    policy: DraftPolicy = Field(default_factory=DraftPolicy)
    other_policies: list[DraftPolicy] = Field(default_factory=list, max_length=MAX_OTHER_PAYERS)
    institutional: DraftInstitutional = Field(default_factory=DraftInstitutional)


class DraftForm(DomainModel):
    """The New Claim form as it was left."""

    patient_id: _optional(PatientId) = None
    payer_id: _optional(PayerId) = None
    other_payer_ids: list[PayerId] = Field(default_factory=list, max_length=MAX_OTHER_PAYERS)
    provider_id: _optional(ProviderId) = None
    facility_id: _optional(FacilityId) = None
    diagnoses: list[Partial] = Field(default_factory=lambda: [""], max_length=MAX_DIAGNOSES)
    lines: list[DraftLine] = Field(default_factory=lambda: [DraftLine()], max_length=50)
    claim_type: ClaimType = ClaimType.PROFESSIONAL
    place_of_service: PlaceOfService = PlaceOfService.OFFICE
    service_date: _optional(date) = None
    submission_date: _optional(date) = None
    pa_required: bool = False
    pa_obtained: bool = False
    pa_number: Annotated[str, StringConstraints(max_length=50)] = ""
    billing: DraftBilling = Field(default_factory=DraftBilling)


class SavedDraft(BaseModel):
    id: DraftId
    form: DraftForm
    created_by: str
    created_at: datetime
    updated_by: str
    updated_at: datetime
    expires_at: datetime


class SavedDraftDetail(SavedDraft):
    """A draft with its patient resolved, for reopening the form."""

    patient: PatientSummary | None = None


class SavedDraftSummary(BaseModel):
    """One row of the Saved drafts list."""

    id: DraftId
    patient_id: PatientId | None
    patient_name: str | None
    lines: int = Field(description="Service lines with a procedure chosen")
    updated_by: str
    updated_at: datetime
    expires_at: datetime
