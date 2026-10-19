"""Conversational RAG chat endpoint."""

import os
from pathlib import Path

from fastapi import APIRouter

from ..models.coverage import ChatRequest, ChatResponse
from ..services.rag import answer_question

router = APIRouter(prefix="/api/chat", tags=["chat"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
CHUNK_DIR = Path(os.getenv("CHUNK_DIR", str(BASE_DIR / "data" / "chunks")))


@router.post("")
async def chat(request: ChatRequest) -> ChatResponse:
    """Answer a question grounded in policy documents."""
    return await answer_question(
        question=request.question,
        chunk_dir=CHUNK_DIR,
        document_id=request.policy_id,
    )
