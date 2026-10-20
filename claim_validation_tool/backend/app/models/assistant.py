"""Clarification assistant: questions, the claim facts it may share, and cited answers."""

from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.aifix import Citation, ClarificationTopic, SourceType
from app.models.common import ClaimId, PayerId


class AssistantMode(StrEnum):
    CLAUDE = "claude"  # Claude writes the answer from the retrieved sources
    RETRIEVAL = "retrieval"  # no LLM: the retrieved sources with a templated summary


class ClaimLineFacts(BaseModel):
    cpt_code: str
    cpt_category: str
    modifier: str | None
    units: int
    charge_amount: float
    icd10_pointer: str


class DenialFacts(BaseModel):
    carc_code: str
    rarc_code: str
    root_cause_category: str
    denial_amount: float
    is_preventable: bool


class ClaimFacts(BaseModel):
    """The only claim data the assistant shares with the LLM: codes and amounts.

    Deliberately excludes anything that identifies the patient or provider (name, patient
    and claim IDs, age, gender, ZIP, provider name/NPI, PA number) and every date element
    finer than the year, as HIPAA's Safe Harbor de-identification method requires.
    """

    claim_type: str
    place_of_service: str
    service_year: int = Field(description="Year of service only, never the month or day")
    status: str
    payer_id: PayerId
    payer_name: str | None
    payer_type: str | None
    other_payer_ids: list[PayerId] = Field(default_factory=list)
    primary_icd10: str
    additional_icd10: list[str] = Field(default_factory=list)
    lines: list[ClaimLineFacts] = Field(default_factory=list)
    total_charge: float
    total_paid: float
    days_in_ar: int
    pa_required: bool
    pa_obtained: bool
    has_pa_number: bool
    denials: list[DenialFacts] = Field(default_factory=list)


class AssistantRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    claim_id: ClaimId | None = Field(default=None, description="Claim the question is about")
    topic: ClarificationTopic | None = Field(
        default=None, description="Focuses retrieval, e.g. the suggestion's clarification topic"
    )


class AssistantSource(Citation):
    label: str = Field(description="How the answer cites it, e.g. S1")
    match_reason: str = Field(description="Why it was retrieved, e.g. which claim code matched")
    cited: bool = Field(description="Whether the answer cites it")


class AssistantAnswer(BaseModel):
    question: str = Field(description="The question as sent, after removing identifiers")
    answer: str = Field(description="Cites sources inline as [S1], [S2]")
    sources: list[AssistantSource]
    mode: AssistantMode
    model: str | None = None
    notice: str | None = Field(default=None, description="e.g. why Claude wasn't used")
    topic: ClarificationTopic | None = None
    claim_facts: ClaimFacts | None = Field(
        default=None, description="Exactly the claim data shared with the LLM"
    )


class AssistantStatus(BaseModel):
    mode: AssistantMode
    model: str | None
    sources: dict[SourceType, int] = Field(description="Knowledge base size by source type")
