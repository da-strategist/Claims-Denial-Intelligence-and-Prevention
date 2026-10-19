"""Conversational RAG chat endpoint."""

import os
from pathlib import Path

from fastapi import APIRouter

from ..models.coverage import ChatRequest, ChatResponse
from ..services.conversations import store
from ..services.rag import answer_question

router = APIRouter(prefix="/api/chat", tags=["chat"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
CHUNK_DIR = Path(os.getenv("CHUNK_DIR", str(BASE_DIR / "data" / "chunks")))


@router.post("")
async def chat(request: ChatRequest) -> ChatResponse:
    """Answer a question grounded in policy documents.

    Pass back the returned `conversation_id` to ask follow-up questions; the
    conversation keeps its policy and recent turns server-side.
    """
    conv = store.get_or_create(request.conversation_id, request.policy_id)
    response = await answer_question(
        question=request.question,
        chunk_dir=CHUNK_DIR,
        document_id=conv.policy_id,
        history=list(conv.turns),
    )
    store.add_turn(conv, request.question, response.answer)
    response.conversation_id = conv.id
    return response
