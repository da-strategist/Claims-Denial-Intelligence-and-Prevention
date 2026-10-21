"""Coverage assessment and prior authorization models."""

from ._compat import StrEnum

from pydantic import BaseModel, Field

from .common import (
    DISCLAIMER,
    MAX_QUESTION_CHARS,
    DocumentId,
    DomainModel,
)


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
    from_scan: bool = False  # the passage was read from a scanned page by OCR


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


class ChatRequest(DomainModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    policy_id: DocumentId | None = None
    patient_id: DocumentId | None = None  # hospital staff: whose policies to search
    conversation_id: DocumentId | None = None


class NextStep(BaseModel):
    """A suggested action, tied to the policy passage that prompted it."""
    text: str
    document_id: str
    page_number: int | None = None
    section: str = ""


class PolicyQuote(BaseModel):
    """A passage shown under "What your policy says"."""
    document_id: str
    document_name: str = ""
    page_number: int | None = None
    section: str = ""
    quote: str
    from_scan: bool = False


class PlanValue(BaseModel):
    document_id: str
    document_name: str = ""
    value: str
    page_number: int | None = None
    section: str = ""


class PlanDifference(BaseModel):
    """An amount the question is about that differs between the plans shown."""
    topic: str
    values: list[PlanValue]


class ChatResponse(BaseModel):
    # The whole answer as plain text (for API clients); the fields below lay
    # it out: lead line, quotes grouped by plan, differences, fixed note.
    answer: str
    lead: str = ""
    policy_says: list[PolicyQuote] = Field(default_factory=list)
    differences: list[PlanDifference] = Field(default_factory=list)
    keep_in_mind: str = ""
    citations: list[SourceCitation] = Field(default_factory=list)
    follow_up_suggestions: list[str] = Field(default_factory=list)
    next_steps: list[NextStep] = Field(default_factory=list)
    confidence: str = "supported"
    conversation_id: str = ""
    disclaimer: str = DISCLAIMER
