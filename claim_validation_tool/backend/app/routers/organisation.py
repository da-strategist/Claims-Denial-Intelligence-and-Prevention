"""The signed-in user's organisation as a whole: exporting all its data (administrators)."""

from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response

from app.data.org_lifecycle import export_organisation
from app.models import Permission
from app.services.auth import SignedIn, audit_note, require
from app.services.org_context import OrgId

router = APIRouter(prefix="/api/organisation", tags=["organisation"])


@router.get("/export", dependencies=[require(Permission.DATA_EXPORT)])
def export(org_id: OrgId, me: SignedIn, request: Request) -> Response:
    """Everything the organisation has here, decrypted, in one zip with a manifest. It holds
    PHI, so the download is recorded in the audit log with what it contained."""
    data, manifest = export_organisation(org_id, me.username)
    audit_note(request, files=len(manifest["files"]), bytes=len(data))
    name = f"{org_id}-export-{datetime.now(UTC):%Y%m%d-%H%M%S}.zip"
    return Response(
        data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"},
    )
