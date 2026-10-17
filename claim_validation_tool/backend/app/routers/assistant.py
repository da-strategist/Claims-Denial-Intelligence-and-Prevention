"""Clarification assistant: cited answers from the reference tables, written by Claude."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.data import ClaimsRepository, KnowledgeBase, get_knowledge_base, get_repository
from app.models import AssistantAnswer, AssistantRequest, AssistantStatus, Permission
from app.services.assistant import (
    AnswerWriter,
    NameScrubber,
    Retriever,
    answer_question,
    claim_facts,
    get_answer_writer,
    get_name_scrubber,
    get_retriever,
)
from app.services.auth import audit_note, require

router = APIRouter(prefix="/api/assistant", tags=["assistant"], dependencies=[require(Permission.CLAIMS_READ)])

Claims = Annotated[ClaimsRepository, Depends(get_repository)]
Writer = Annotated[AnswerWriter, Depends(get_answer_writer)]


@router.post("", response_model=AssistantAnswer)
def ask(
    request: AssistantRequest,
    http: Request,
    claims: Claims,
    retriever: Annotated[Retriever, Depends(get_retriever)],
    writer: Writer,
    names: Annotated[NameScrubber, Depends(get_name_scrubber)],
) -> AssistantAnswer:
    """Answer a billing question from the reference tables, citing them as [S1], [S2].

    With a `claim_id`, the claim's codes guide retrieval and only its codes and amounts
    (`claim_facts` in the response) are shared with the LLM. IDs, dates, and the names of
    registered patients and providers are masked in the question first.
    """
    audit_note(http, claim_id=request.claim_id, topic=request.topic)
    facts = None
    if request.claim_id:
        claim = claims.get_claim(request.claim_id)
        if claim is None:
            raise HTTPException(status_code=404, detail=f"Claim {request.claim_id} not found")
        facts = claim_facts(claim)
    return answer_question(request.question, facts, request.topic, retriever, writer, names)


@router.get("/status", response_model=AssistantStatus)
def status(
    knowledge: Annotated[KnowledgeBase, Depends(get_knowledge_base)], writer: Writer
) -> AssistantStatus:
    """Whether Claude writes the answers, and what the knowledge base holds."""
    return AssistantStatus(mode=writer.mode, model=writer.model, sources=knowledge.counts())
