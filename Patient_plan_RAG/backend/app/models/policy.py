"""Insurance policy and document models."""

from datetime import date
from ._compat import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from .common import DISCLAIMER, DomainModel


class DocumentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class PolicyDocument(DomainModel):
    """An uploaded or preloaded insurance policy document."""
    document_id: str
    filename: str
    insurer_name: str = ""
    plan_name: str = ""
    plan_id: str = ""
    effective_date: date | None = None
    expiration_date: date | None = None
    document_type: str = "policy"  # policy, sbc, eob, auth_guide
    status: DocumentStatus = DocumentStatus.PENDING
    page_count: int = 0
    chunk_count: int = 0
    chunker_version: int = 0  # 0 = ingested before versioning
    # Exactly one owner kind (see auth/access.py): an individual (`owner`),
    # a hospital patient record (`org_id` + `patient_id`), or neither = sample.
    owner: str | None = None
    org_id: str | None = None
    patient_id: str | None = None
    is_synthetic: bool = True
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    """A retrieval-ready chunk of a policy document."""
    chunk_id: str
    document_id: str
    page_number: int | None = None
    section_heading: str = ""
    content: str
    content_lower: str = ""  # for keyword search
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicySummary(BaseModel):
    """Structured summary of a policy's key provisions."""
    document_id: str
    plan_overview: str = ""
    covered_services: list[dict[str, str]] = Field(default_factory=list)
    excluded_services: list[dict[str, str]] = Field(default_factory=list)
    deductible: dict[str, str] = Field(default_factory=dict)
    copayments: list[dict[str, str]] = Field(default_factory=list)
    coinsurance: dict[str, str] = Field(default_factory=dict)
    out_of_pocket_max: dict[str, str] = Field(default_factory=dict)
    network_provisions: dict[str, str] = Field(default_factory=dict)
    prior_auth_services: list[dict[str, str]] = Field(default_factory=list)
    referral_requirements: str = ""
    important_limitations: list[str] = Field(default_factory=list)
    source_references: list[dict[str, Any]] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: DocumentStatus
    page_count: int = 0
    message: str = ""
    disclaimer: str = DISCLAIMER
