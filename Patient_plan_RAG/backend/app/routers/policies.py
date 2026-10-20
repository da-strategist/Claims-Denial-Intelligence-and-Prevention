"""Policy document upload, listing, and summary endpoints."""

import os
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, UploadFile
from fastapi import Path as PathParam

from ..audit import audit_document, audit_patient
from ..auth.access import Access, entry_or_404
from ..auth.sessions import Permission, require
from ..auth.users import HOSPITAL_ROLES, Role, User
from ..models.common import DISCLAIMER, DOCUMENT_ID_PATTERN
from ..models.policy import (
    DocumentStatus,
    DocumentUploadResponse,
    PolicyDocument,
    PolicySummary,
)
from ..services import registry
from ..services.document_processor import process_document
from ..services.policy_summarizer import summarize_policy
from ..services.retrieval import load_chunks

router = APIRouter(prefix="/api/policies", tags=["policies"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "data" / "uploads")))
CHUNK_DIR = Path(os.getenv("CHUNK_DIR", str(BASE_DIR / "data" / "chunks")))
MAX_UPLOAD_BYTES = int(float(os.getenv("MAX_UPLOAD_MB", "20")) * 1024 * 1024)

DocumentIdParam = PathParam(pattern=DOCUMENT_ID_PATTERN)


def _safe_filename(name: str) -> str:
    """Basename only, restricted alphabet, bounded length."""
    base = Path(name.replace("\\", "/")).name
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base).lstrip(".")
    return base[-100:] or "upload.pdf"


_read = require(Permission.READ_POLICIES)


@router.get("")
async def list_policies(user: User = Depends(_read)) -> list[PolicyDocument]:
    """The policy documents this user may see (see auth/access.py)."""
    return [PolicyDocument(**r) for r in Access(user).visible(registry.load())]


@router.get("/{document_id}")
async def get_policy(document_id: str = DocumentIdParam,
                     user: User = Depends(_read)) -> PolicyDocument:
    """A single policy document's metadata."""
    return PolicyDocument(**entry_or_404(user, registry.load(), document_id))


@router.post("/upload")
async def upload_policy(
    file: UploadFile, request: Request,
    patient_id: str | None = Form(None, pattern=DOCUMENT_ID_PATTERN),
    user: User = Depends(require(Permission.UPLOAD_POLICY)),
) -> DocumentUploadResponse:
    """Upload and process a PDF policy document.

    Individuals: private to them. Hospital staff: filed under one of their
    hospital's patients (`patient_id` required). Platform admin: a sample.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")
    if user.role in HOSPITAL_ROLES:
        if not patient_id:
            raise HTTPException(400, "Choose the patient this policy belongs to")
        Access(user).patient_or_404(patient_id)
        ownership = {"org_id": user.org_id, "patient_id": patient_id}
    elif patient_id:
        raise HTTPException(400, "Only hospital staff file documents under a patient")
    elif user.role is Role.INDIVIDUAL:
        ownership = {"owner": user.username}
    else:  # platform admin
        ownership = {}

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

    doc, chunks = process_document(dest, CHUNK_DIR, metadata=ownership)

    entries = registry.load()
    entries.append(doc.model_dump(mode="json"))
    registry.save(entries)
    audit_document(request, doc.document_id)
    audit_patient(request, patient_id)

    return DocumentUploadResponse(
        document_id=doc.document_id,
        filename=doc.filename,
        status=doc.status,
        page_count=doc.page_count,
        message=f"Processed {doc.chunk_count} text chunks from {doc.page_count} pages",
    )


@router.get("/{document_id}/summary")
async def get_policy_summary(document_id: str = DocumentIdParam,
                             user: User = Depends(_read)) -> PolicySummary:
    """Generate or retrieve a structured summary of the policy."""
    entry_or_404(user, registry.load(), document_id)

    chunks = load_chunks(CHUNK_DIR, document_id)
    if not chunks:
        raise HTTPException(404, "No processed chunks found for this document")

    return summarize_policy(document_id, chunks)


@router.get("/{document_id}/chunks")
async def get_policy_chunks(
    document_id: str = DocumentIdParam,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(_read),
):
    """List chunks for a document (paginated)."""
    entry_or_404(user, registry.load(), document_id)
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
