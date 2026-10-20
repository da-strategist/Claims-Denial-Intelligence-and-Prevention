"""Conversational RAG chat endpoint."""

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from ..audit import audit_document, audit_patient
from ..auth.access import Access
from ..auth.sessions import Permission, require
from ..auth.users import HOSPITAL_ROLES, User
from ..models.coverage import ChatRequest, ChatResponse
from ..services import registry
from ..services.conversations import store
from ..services.rag import answer_question

router = APIRouter(prefix="/api/chat", tags=["chat"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
CHUNK_DIR = Path(os.getenv("CHUNK_DIR", str(BASE_DIR / "data" / "chunks")))


@router.post("")
async def chat(request: ChatRequest, http: Request,
               user: User = Depends(require(Permission.ASK))) -> ChatResponse:
    """Answer a question grounded in the policy documents this user may see.

    Pass back the returned `conversation_id` to ask follow-up questions; the
    conversation keeps its policy and recent turns server-side, and only its
    owner can continue it.
    """
    entries = registry.load()
    access = Access(user)
    if request.policy_id:
        access.entry_or_404(entries, request.policy_id)
    if request.patient_id:
        access.patient_or_404(request.patient_id)
    if user.role in HOSPITAL_ROLES and not (request.policy_id or request.patient_id):
        # never search across several patients at once
        raise HTTPException(400, "Choose a patient or a policy document first")

    conv = store.get_or_create(request.conversation_id, request.policy_id,
                               owner=user.username, patient_id=request.patient_id)
    audit_document(http, conv.policy_id)
    audit_patient(http, conv.patient_id)
    # access may have been revoked since the conversation began
    if conv.policy_id:
        access.entry_or_404(entries, conv.policy_id)
    if conv.patient_id:
        access.patient_or_404(conv.patient_id)
    response = await answer_question(
        question=request.question,
        chunk_dir=CHUNK_DIR,
        document_id=conv.policy_id,
        history=list(conv.turns),
        allowed_ids=access.default_search_ids(entries, conv.patient_id),
    )
    store.add_turn(conv, request.question, response.answer)
    response.conversation_id = conv.id
    return response
