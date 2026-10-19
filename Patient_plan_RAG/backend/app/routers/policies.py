"""Policy document upload, listing, and summary endpoints."""

import json
import os
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi import Path as PathParam

from ..models.common import DISCLAIMER, DOCUMENT_ID_PATTERN
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
MAX_UPLOAD_BYTES = int(float(os.getenv("MAX_UPLOAD_MB", "20")) * 1024 * 1024)

DocumentIdParam = PathParam(pattern=DOCUMENT_ID_PATTERN)


def _safe_filename(name: str) -> str:
    """Basename only, restricted alphabet, bounded length."""
    base = Path(name.replace("\\", "/")).name
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base).lstrip(".")
    return base[-100:] or "upload.pdf"


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
async def get_policy(document_id: str = DocumentIdParam) -> PolicyDocument:
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
    dest = UPLOAD_DIR / f"{uuid.uuid4().hex[:8]}_{_safe_filename(file.filename)}"
    size = 0
    try:
        with open(dest, "wb") as f:
            while block := file.file.read(1024 * 1024):
                if size == 0 and not block.startswith(b"%PDF-"):
                    raise HTTPException(400, "File is not a PDF")
                size += len(block)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        413, f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit")
                f.write(block)
        if size == 0:
            raise HTTPException(400, "File is empty")
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise

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
async def get_policy_summary(document_id: str = DocumentIdParam) -> PolicySummary:
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
async def get_policy_chunks(
    document_id: str = DocumentIdParam,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
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
