"""Dashboard stats endpoint."""

import json
import os
from pathlib import Path

from fastapi import APIRouter

from ..services.retrieval import load_chunks

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
POLICY_DIR = Path(os.getenv("POLICY_DIR", str(BASE_DIR / "data" / "policies")))
CHUNK_DIR = Path(os.getenv("CHUNK_DIR", str(BASE_DIR / "data" / "chunks")))


@router.get("")
async def dashboard_stats():
    """Return summary stats for the dashboard."""
    registry_path = POLICY_DIR / "_registry.json"
    policies = []
    if registry_path.exists():
        policies = json.loads(registry_path.read_text())

    total_chunks = 0
    total_pages = 0
    for p in policies:
        total_pages += p.get("page_count", 0)
        total_chunks += p.get("chunk_count", 0)

    return {
        "total_policies": len(policies),
        "total_pages": total_pages,
        "total_chunks": total_chunks,
        "mode": os.getenv("APP_MODE", "demo"),
        "policies": [
            {
                "document_id": p["document_id"],
                "filename": p["filename"],
                "status": p["status"],
                "page_count": p.get("page_count", 0),
                "chunk_count": p.get("chunk_count", 0),
                "insurer_name": p.get("insurer_name", ""),
                "plan_name": p.get("plan_name", ""),
            }
            for p in policies
        ],
    }
