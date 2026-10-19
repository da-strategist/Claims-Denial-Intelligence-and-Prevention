"""Dashboard stats endpoint."""

import os

from fastapi import APIRouter, Depends

from ..auth.access import can_access
from ..auth.sessions import Permission, require
from ..auth.users import User
from ..models.common import DISCLAIMER
from ..services import registry

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])



@router.get("")
async def dashboard_stats(user: User = Depends(require(Permission.VIEW_DASHBOARD))):
    """Summary stats over the policies this user may see."""
    policies = [p for p in registry.load() if can_access(user, p)]

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
        "disclaimer": DISCLAIMER,
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
