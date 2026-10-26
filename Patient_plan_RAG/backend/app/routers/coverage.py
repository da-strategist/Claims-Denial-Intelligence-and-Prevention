"""Coverage assessment and prior authorization checklist endpoints."""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from pydantic import Field

from ..audit import audit_document
from ..auth.access import entry_or_404
from ..auth.sessions import Permission, require
from ..auth.users import User
from ..models.common import (
    MAX_CODE_CHARS,
    MAX_SERVICE_CHARS,
    DocumentId,
    DomainModel,
)
from ..models.coverage import (
    AuthorizationChecklist,
    AuthReadiness,
    ChecklistItem,
    CoverageAssessment,
    SourceCitation,
)
from ..services import registry
from ..services.coverage_assessor import assess_coverage as assess_service
from ..services.retrieval import adapt_vocabulary, load_chunks, retrieve

router = APIRouter(prefix="/api/coverage", tags=["coverage"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
CHUNK_DIR = Path(os.getenv("CHUNK_DIR", str(BASE_DIR / "data" / "chunks")))


class AssessmentRequest(DomainModel):
    service_name: str = Field(min_length=1, max_length=MAX_SERVICE_CHARS)
    service_code: str = Field("", max_length=MAX_CODE_CHARS)
    document_id: DocumentId


class AuthChecklistRequest(DomainModel):
    service_name: str = Field(min_length=1, max_length=MAX_SERVICE_CHARS)
    service_code: str = Field("", max_length=MAX_CODE_CHARS)
    document_id: DocumentId
    diagnosis_code: str = Field("", max_length=MAX_CODE_CHARS)


@router.post("/assess")
async def assess_coverage(req: AssessmentRequest, http: Request,
                          user: User = Depends(require(Permission.ASK))) -> CoverageAssessment:
    """Assess whether a service is covered under a policy."""
    audit_document(http, req.document_id)
    entry_or_404(user, registry.load(), req.document_id)
    chunks = load_chunks(CHUNK_DIR, req.document_id)
    return assess_service(req.service_name, req.service_code, chunks)


@router.post("/auth-checklist")
async def generate_auth_checklist(
    req: AuthChecklistRequest, http: Request, user: User = Depends(require(Permission.ASK)),
) -> AuthorizationChecklist:
    """Generate a prior authorization preparation checklist."""
    audit_document(http, req.document_id)
    entry_or_404(user, registry.load(), req.document_id)
    chunks = load_chunks(CHUNK_DIR, req.document_id)
    # "prior authorization" becomes the policy's own term (precertification, advance approval, ...)
    query = adapt_vocabulary(
        f"prior authorization requirements {req.service_name} {req.service_code} {req.diagnosis_code}",
        chunks)
    results = retrieve(query, chunks, top_k=6)

    checklist_id = uuid.uuid4().hex[:12]
    items: list[ChecklistItem] = []

    # Standard items always needed
    standard_items = [
        ("proc-1", "procedure", f"CPT/HCPCS code for {req.service_name}", True),
        ("diag-1", "diagnosis", "ICD-10 diagnosis code(s) supporting medical necessity", True),
        ("prov-1", "provider", "Ordering/referring provider NPI and credentials", True),
        ("prov-2", "provider", "Servicing/rendering provider NPI", True),
        ("clin-1", "clinical", "Clinical notes supporting medical necessity", True),
        ("ref-1", "referral", "Specialist referral (if required by plan)", False),
    ]
    for item_id, cat, desc, req_flag in standard_items:
        items.append(ChecklistItem(
            item_id=item_id,
            category=cat,
            description=desc,
            required=req_flag,
            source="suggested",
        ))

    # Add policy-specific items from retrieved chunks
    citations = []
    for chunk, score in results:
        citations.append(SourceCitation(
            document_id=chunk.document_id,
            page_number=chunk.page_number,
            section=chunk.section_heading,
            from_scan=bool(chunk.metadata.get("from_scan")),
            excerpt=chunk.content[:250],
            confidence="supported" if score > 0.3 else "interpreted",
        ))
        # Extract requirements from text
        content_lower = chunk.content.lower()
        if "letter of medical necessity" in content_lower:
            items.append(ChecklistItem(
                item_id=f"pol-{len(items)}",
                category="clinical",
                description="Letter of Medical Necessity from treating provider",
                required=True,
                source="policy",
            ))
        if "peer-to-peer" in content_lower or "peer to peer" in content_lower:
            items.append(ChecklistItem(
                item_id=f"pol-{len(items)}",
                category="clinical",
                description="Peer-to-peer review may be requested",
                required=False,
                source="policy",
            ))
        if "failed" in content_lower and "conservative" in content_lower:
            items.append(ChecklistItem(
                item_id=f"pol-{len(items)}",
                category="clinical",
                description="Documentation of failed conservative treatment",
                required=True,
                source="policy",
            ))

    readiness = AuthReadiness.MISSING if items else AuthReadiness.UNCLEAR
    missing_count = sum(1 for i in items if i.required and not i.completed)

    return AuthorizationChecklist(
        checklist_id=checklist_id,
        service_name=req.service_name,
        service_code=req.service_code,
        policy_document_id=req.document_id,
        readiness=readiness,
        items=items,
        missing_count=missing_count,
        completed_count=0,
        citations=citations,
    )
