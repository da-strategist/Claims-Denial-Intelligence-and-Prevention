"""Coverage assessment and prior authorization models."""

from ._compat import StrEnum

from pydantic import BaseModel, Field

from .common import DISCLAIMER


class CoverageClassification(StrEnum):
    COVERED = "coverage_indicated"
    CONDITIONAL = "conditional_coverage"
    EXCLUDED = "exclusion_identified"
    INSUFFICIENT = "insufficient_information"
    CONFIRM = "confirmation_required"


class AuthReadiness(StrEnum):
    READY = "ready_for_review"
    MISSING = "missing_information"
    UNCLEAR = "requirements_unclear"
    CONFIRM_NEEDED = "confirmation_needed"


class SourceCitation(BaseModel):
    """A reference to a specific policy passage."""
    document_id: str
    document_name: str = ""
    page_number: int | None = None
    section: str = ""
    excerpt: str = ""
    confidence: str = "supported"  # supported, interpreted, suggested


class CoverageAssessment(BaseModel):
    """Assessment of a service against available policy evidence."""
    service_name: str
    service_code: str = ""
    classification: CoverageClassification
    explanation: str
    conditions: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    cost_sharing: dict[str, str] = Field(default_factory=dict)
    network_notes: str = ""
    referral_required: bool | None = None
    prior_auth_required: bool | None = None
    missing_information: list[str] = Field(default_factory=list)
    recommended_steps: list[str] = Field(default_factory=list)
    citations: list[SourceCitation] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER


class ChecklistItem(BaseModel):
    """A single item in an authorization checklist."""
    item_id: str
    category: str  # procedure, diagnosis, provider, clinical, referral, form
    description: str
    required: bool = True
    source: str = "policy"  # policy, suggested, verification
    completed: bool = False
    value: str = ""
    notes: str = ""


class AuthorizationChecklist(BaseModel):
    """Prior authorization preparation checklist."""
    checklist_id: str
    service_name: str
    service_code: str = ""
    policy_document_id: str
    readiness: AuthReadiness
    items: list[ChecklistItem] = Field(default_factory=list)
    draft_request: str = ""
    missing_count: int = 0
    completed_count: int = 0
    citations: list[SourceCitation] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER


class ChatMessage(BaseModel):
    role: str  # user, assistant
    content: str
    citations: list[SourceCitation] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class ChatRequest(BaseModel):
    question: str
    policy_id: str | None = None
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[SourceCitation] = Field(default_factory=list)
    follow_up_suggestions: list[str] = Field(default_factory=list)
    confidence: str = "supported"
    conversation_id: str = ""
    disclaimer: str = DISCLAIMER
