"""What the 837 claim file needs beyond the claim itself: the patient's demographics, who
holds each insurance policy, and (for institutional claims) the UB-04 header codes.

These come in with the claim, from the New Claim form or the API. They are PHI, so only
roles that can see patient details get them back.
"""

from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints, model_validator

from app.models.common import DomainModel, _blank_to_none

Name = Annotated[str, StringConstraints(min_length=1, max_length=60, strip_whitespace=True)]
OptionalText = Annotated[
    Annotated[str, StringConstraints(max_length=55)] | None, BeforeValidator(_blank_to_none)
]


class Sex(StrEnum):
    FEMALE = "F"
    MALE = "M"
    UNKNOWN = "U"


class Relationship(StrEnum):
    """The patient's relationship to the person who holds the policy."""

    SELF = "self"
    SPOUSE = "spouse"
    CHILD = "child"
    OTHER = "other"


# X12 individual relationship codes (SBR02 / PAT01)
RELATIONSHIP_CODES = {
    Relationship.SELF: "18",
    Relationship.SPOUSE: "01",
    Relationship.CHILD: "19",
    Relationship.OTHER: "G8",
}


class Address(DomainModel):
    line1: Annotated[str, StringConstraints(min_length=1, max_length=55, strip_whitespace=True)]
    line2: OptionalText = None
    city: Annotated[str, StringConstraints(min_length=2, max_length=30, strip_whitespace=True)]
    state: Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")]
    zip_code: Annotated[str, StringConstraints(pattern=r"^\d{5}(\d{4})?$")]


class PolicyHolder(DomainModel):
    """Who holds an insurance policy. When it's the patient, their own details are used."""

    member_id: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9-]{2,30}$")]
    group_number: Annotated[
        Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9-]{1,30}$")] | None,
        BeforeValidator(_blank_to_none),
    ] = None
    relationship: Relationship = Relationship.SELF
    # Only when the policy holder isn't the patient
    first_name: Name | None = None
    last_name: Name | None = None
    birth_date: date | None = None
    sex: Sex | None = None

    @model_validator(mode="after")
    def _holder_details(self) -> "PolicyHolder":
        if self.relationship != Relationship.SELF:
            missing = [
                field
                for field in ("first_name", "last_name", "birth_date", "sex")
                if getattr(self, field) is None
            ]
            if missing:
                raise ValueError(
                    "When the patient isn't the policy holder, give the holder's "
                    + ", ".join(missing)
                )
        return self


class InstitutionalDetails(DomainModel):
    """UB-04 header codes an 837I needs."""

    type_of_bill: Annotated[
        str, StringConstraints(pattern=r"^[1-9][1-9][0-9A-Z]$")
    ] = Field(description="Facility type, classification, and frequency, e.g. 131")
    admission_type: Annotated[str, StringConstraints(pattern=r"^[1-59]$")] = Field(
        description="1 emergency, 2 urgent, 3 elective, 4 newborn, 5 trauma, 9 unknown"
    )
    admission_source: Annotated[str, StringConstraints(pattern=r"^[0-9A-Z]$")] = Field(
        description="Point of origin, e.g. 1 non-health-care facility, 2 clinic referral"
    )
    patient_status: Annotated[str, StringConstraints(pattern=r"^\d{2}$")] = Field(
        description="Discharge status, e.g. 01 discharged home"
    )


class ClaimBilling(DomainModel):
    """Everything the 837 needs that the claim header doesn't carry."""

    patient_birth_date: date
    patient_address: Address
    policy: PolicyHolder | None = Field(
        default=None, description="The billed payer's policy; not needed for self-pay"
    )
    other_policies: list[PolicyHolder] = Field(
        default_factory=list,
        max_length=2,
        description="One per other payer on the claim, in the same order",
    )
    institutional: InstitutionalDetails | None = Field(
        default=None, description="Required on institutional claims"
    )


class EdiFile(BaseModel):
    """The 837 created when a claim was submitted (its text is downloaded separately)."""

    transaction: str = Field(description="837P (professional) or 837I (institutional)")
    control_number: str
    generated_at: str
    test: bool = Field(description="Marked as a test file (ISA15 = T)")
    notes: list[str] = Field(
        default_factory=list, description="Why it's a test file: settings still to fill in"
    )


class RegistrationSource(StrEnum):
    SAMPLE = "sample"  # generated for the synthetic sample patients
    ENTERED = "entered"  # captured from a claim (New Claim form or API)


class PatientRegistration(BaseModel):
    """A registered patient's billing details, filled into each new claim for them.

    Sample patients start with generated details; the first claim entered for a patient
    replaces them with what was captured, and later claims reuse that.
    """

    patient_id: str
    birth_date: date
    sex: Sex
    address: Address
    policies: dict[str, PolicyHolder] = Field(
        default_factory=dict, description="Policy details by payer ID"
    )
    source: RegistrationSource
    updated_at: str | None = None
    updated_by: str | None = None
