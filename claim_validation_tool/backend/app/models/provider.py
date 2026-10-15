"""Rendering provider model — mirrors dim_providers.csv."""

from enum import StrEnum

from pydantic import Field

from app.models.common import DepartmentId, DomainModel, Npi, ProviderId, Ratio, RecordStatus


class Credential(StrEnum):
    MD = "MD"
    DO = "DO"
    NP = "NP"
    PA = "PA"


class Provider(DomainModel):
    provider_id: ProviderId
    provider_name: str
    npi: Npi
    specialty: str
    department_id: DepartmentId
    coding_accuracy_score: Ratio
    documentation_completeness_score: Ratio
    years_experience: int = Field(ge=0)
    status: RecordStatus
    credential: Credential
