"""Patient model — mirrors dim_patients.csv (the hospital's registered patients)."""

from pydantic import BaseModel, Field

from app.models.common import DomainModel, PatientId, PayerId, RecordStatus


class Patient(DomainModel):
    patient_id: PatientId
    first_name: str
    last_name: str
    age: int = Field(ge=0)
    gender: str
    primary_payer_id: PayerId
    zip_code: str
    language: str
    status: RecordStatus


class PatientSummary(Patient):
    """Patient plus claim history, for picking the right patient when entering a claim."""

    claim_count: int = Field(ge=0)
    denial_count: int = Field(ge=0)


class PatientQuery(BaseModel):
    search: str | None = Field(
        default=None, description="Patient ID, or first and/or last name (case-insensitive)"
    )
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)
