"""Policy document upload, listing, and summary endpoints."""

import json
import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from ..models.common import DISCLAIMER
from ..models.policy import (
    DocumentStatus,
    DocumentUploadResponse,
    PolicyDocument,
    PolicySummary,
)
from ..services.document_processor import process_document
from ..services.policy_summarizer import summarize_policy
from ..services.retrieval import load_chunks

router = APIRouter(prefix="/api/policies", tags=["policies"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "data" / "uploads")))
POLICY_DIR = Path(os.getenv("POLICY_DIR", str(BASE_DIR / "data" / "policies")))
CHUNK_DIR = Path(os.getenv("CHUNK_DIR", str(BASE_DIR / "data" / "chunks")))


def _load_registry() -> list[dict]:
    path = POLICY_DIR / "_registry.json"
    if path.exists():
        return json.loads(path.read_text())
    return []


def _save_registry(registry: list[dict]) -> None:
    path = POLICY_DIR / "_registry.json"
    path.write_text(json.dumps(registry, indent=2, default=str))


@router.get("")
async def list_policies() -> list[PolicyDocument]:
    """List all ingested policy documents."""
    registry = _load_registry()
    return [PolicyDocument(**r) for r in registry]


@router.get("/{document_id}")
async def get_policy(document_id: str) -> PolicyDocument:
    """Get a single policy document's metadata."""
    for r in _load_registry():
        if r["document_id"] == document_id:
            return PolicyDocument(**r)
    raise HTTPException(404, f"Document {document_id} not found")


@router.post("/upload")
async def upload_policy(file: UploadFile) -> DocumentUploadResponse:
    """Upload and process a PDF policy document."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / f"{uuid.uuid4().hex[:8]}_{file.filename}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    doc, chunks = process_document(dest, CHUNK_DIR)

    # Update registry
    registry = _load_registry()
    registry.append(doc.model_dump(mode="json"))
    _save_registry(registry)

    return DocumentUploadResponse(
        document_id=doc.document_id,
        filename=doc.filename,
        status=doc.status,
        page_count=doc.page_count,
        message=f"Processed {doc.chunk_count} text chunks from {doc.page_count} pages",
    )


@router.get("/{document_id}/summary")
async def get_policy_summary(document_id: str) -> PolicySummary:
    """Generate or retrieve a structured summary of the policy."""
    # Verify document exists
    found = False
    for r in _load_registry():
        if r["document_id"] == document_id:
            found = True
            break
    if not found:
        raise HTTPException(404, f"Document {document_id} not found")

    chunks = load_chunks(CHUNK_DIR, document_id)
    if not chunks:
        raise HTTPException(404, "No processed chunks found for this document")

    return summarize_policy(document_id, chunks)


@router.get("/{document_id}/chunks")
async def get_policy_chunks(document_id: str, page: int = 1, page_size: int = 20):
    """List chunks for a document (paginated)."""
    chunks = load_chunks(CHUNK_DIR, document_id)
    total = len(chunks)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": [c.model_dump() for c in chunks[start:end]],
        "total": total,
        "page": page,
        "page_size": page_size,
        "disclaimer": DISCLAIMER,
    }
