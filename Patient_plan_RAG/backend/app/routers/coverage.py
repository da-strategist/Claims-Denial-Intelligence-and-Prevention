"""Coverage assessment and prior authorization checklist endpoints."""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..models.coverage import (
    AuthorizationChecklist,
    AuthReadiness,
    ChecklistItem,
    CoverageAssessment,
    CoverageClassification,
    SourceCitation,
)
from ..services.retrieval import retrieve_for_policy

router = APIRouter(prefix="/api/coverage", tags=["coverage"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
CHUNK_DIR = Path(os.getenv("CHUNK_DIR", str(BASE_DIR / "data" / "chunks")))


class AssessmentRequest(BaseModel):
    service_name: str
    service_code: str = ""
    document_id: str


class AuthChecklistRequest(BaseModel):
    service_name: str
    service_code: str = ""
    document_id: str
    diagnosis_code: str = ""


@router.post("/assess")
async def assess_coverage(req: AssessmentRequest) -> CoverageAssessment:
    """Assess whether a service is covered under a policy."""
    # Generic words like "coverage"/"benefit" would outrank the service itself
    # (they match the plan title), so search on the service alone.
    query = f"{req.service_name} {req.service_code}"
    results = retrieve_for_policy(query, CHUNK_DIR, req.document_id, top_k=6)

    if not results:
        return CoverageAssessment(
            service_name=req.service_name,
            service_code=req.service_code,
            classification=CoverageClassification.INSUFFICIENT,
            explanation=(
                "Insufficient policy evidence was found to assess coverage for "
                f"'{req.service_name}'. The policy may not specifically address "
                "this service, or it may be listed under different terminology."
            ),
            missing_information=["Policy may not address this service explicitly"],
            recommended_steps=[
                "Contact plan administrator for coverage verification",
                "Request a predetermination of benefits",
            ],
        )

    citations = []
    conditions = []
    exclusions = []
    for chunk, score in results:
        citations.append(SourceCitation(
            document_id=chunk.document_id,
            page_number=chunk.page_number,
            section=chunk.section_heading,
            excerpt=chunk.content[:250],
            confidence="supported" if score > 0.3 else "interpreted",
        ))
        content_lower = chunk.content.lower()
        if any(kw in content_lower for kw in ["not covered", "excluded", "does not"]):
            exclusions.append(chunk.content[:150])
        if any(kw in content_lower for kw in ["requires", "condition", "must", "prior"]):
            conditions.append(chunk.content[:150])

    # Simple classification heuristic
    if exclusions and not conditions:
        classification = CoverageClassification.EXCLUDED
    elif conditions:
        classification = CoverageClassification.CONDITIONAL
    else:
        classification = CoverageClassification.COVERED

    top_chunk = results[0][0]
    return CoverageAssessment(
        service_name=req.service_name,
        service_code=req.service_code,
        classification=classification,
        explanation=(
            f"Based on policy evidence from section '{top_chunk.section_heading or 'General'}' "
            f"(page {top_chunk.page_number or '?'}), {req.service_name} appears to be "
            f"{classification.value.replace('_', ' ')}. "
            "Review the cited passages for full context."
        ),
        conditions=conditions[:3],
        exclusions=exclusions[:3],
        prior_auth_required=bool(
            any("prior auth" in c.content.lower() or "preauthorization" in c.content.lower()
                for c, _ in results)
        ),
        citations=citations,
        recommended_steps=[
            "Verify with plan administrator",
            "Check for applicable medical necessity criteria",
        ],
    )


@router.post("/auth-checklist")
async def generate_auth_checklist(req: AuthChecklistRequest) -> AuthorizationChecklist:
    """Generate a prior authorization preparation checklist."""
    query = (
        f"prior authorization precertification requirements {req.service_name} "
        f"{req.service_code} {req.diagnosis_code}"
    )
    results = retrieve_for_policy(query, CHUNK_DIR, req.document_id, top_k=6)

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
