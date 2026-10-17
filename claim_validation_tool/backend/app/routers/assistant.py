"""Clarification assistant: cited answers from the reference tables, written by Claude."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.data import ClaimsRepository, KnowledgeBase, get_knowledge_base, get_repository
from app.models import AssistantAnswer, AssistantRequest, AssistantStatus
from app.services.assistant import (
    AnswerWriter,
    Retriever,
    answer_question,
    claim_facts,
    get_answer_writer,
    get_retriever,
)

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

Claims = Annotated[ClaimsRepository, Depends(get_repository)]
Writer = Annotated[AnswerWriter, Depends(get_answer_writer)]


@router.post("", response_model=AssistantAnswer)
def ask(
    request: AssistantRequest,
    claims: Claims,
    retriever: Annotated[Retriever, Depends(get_retriever)],
    writer: Writer,
) -> AssistantAnswer:
    """Answer a billing question from the reference tables, citing them as [S1], [S2].

    With a `claim_id`, the claim's codes guide retrieval and only its codes and amounts
    (`claim_facts` in the response) are shared with the LLM.
    """
    facts = None
    if request.claim_id:
        claim = claims.get_claim(request.claim_id)
        if claim is None:
            raise HTTPException(status_code=404, detail=f"Claim {request.claim_id} not found")
        facts = claim_facts(claim)
    return answer_question(request.question, facts, request.topic, retriever, writer)


@router.get("/status", response_model=AssistantStatus)
def status(
    knowledge: Annotated[KnowledgeBase, Depends(get_knowledge_base)], writer: Writer
) -> AssistantStatus:
    """Whether Claude writes the answers, and what the knowledge base holds."""
    return AssistantStatus(mode=writer.mode, model=writer.model, sources=knowledge.counts())
