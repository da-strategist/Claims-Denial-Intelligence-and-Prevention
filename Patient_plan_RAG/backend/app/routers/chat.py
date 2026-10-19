"""Conversational RAG chat endpoint."""

import os
from pathlib import Path

from fastapi import APIRouter, Depends

from ..auth.access import accessible_ids, entry_or_404
from ..auth.sessions import Permission, require
from ..auth.users import User
from ..models.coverage import ChatRequest, ChatResponse
from ..services import registry
from ..services.conversations import store
from ..services.rag import answer_question

router = APIRouter(prefix="/api/chat", tags=["chat"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
CHUNK_DIR = Path(os.getenv("CHUNK_DIR", str(BASE_DIR / "data" / "chunks")))


@router.post("")
async def chat(request: ChatRequest,
               user: User = Depends(require(Permission.ASK))) -> ChatResponse:
    """Answer a question grounded in the policy documents this user may see.

    Pass back the returned `conversation_id` to ask follow-up questions; the
    conversation keeps its policy and recent turns server-side, and only its
    owner can continue it.
    """
    entries = registry.load()
    if request.policy_id:
        entry_or_404(user, entries, request.policy_id)
    conv = store.get_or_create(request.conversation_id, request.policy_id, owner=user.username)
    if conv.policy_id:  # access may have been revoked since the conversation began
        entry_or_404(user, entries, conv.policy_id)
    response = await answer_question(
        question=request.question,
        chunk_dir=CHUNK_DIR,
        document_id=conv.policy_id,
        history=list(conv.turns),
        allowed_ids=accessible_ids(user, entries),
    )
    store.add_turn(conv, request.question, response.answer)
    response.conversation_id = conv.id
    return response
