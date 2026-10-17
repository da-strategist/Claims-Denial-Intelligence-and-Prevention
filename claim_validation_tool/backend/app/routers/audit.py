"""Read the audit log (admins only), and see or end the platform's emergency access to
the organisation. Reading it is itself recorded."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from app.data.emergency import EmergencyAccess, get_emergency_access
from app.models import AuditEvent, AuditQuery, AuditVerification, Permission
from app.services.auth import SignedIn, audit_note, require
from app.services.org_context import OrgAudit, OrgId

router = APIRouter(
    prefix="/api/audit", tags=["audit"], dependencies=[require(Permission.AUDIT_READ)]
)

Log = OrgAudit


@router.get("", response_model=list[AuditEvent])
def list_events(query: Annotated[AuditQuery, Query()], log: Log) -> list[AuditEvent]:
    """Recent events, newest first, filtered by user, record ID, or outcome."""
    return log.search(query)


@router.get("/verify", response_model=AuditVerification)
def verify(log: Log) -> AuditVerification:
    """Check the hash chain: has any event been edited or removed?"""
    return log.verify()


@router.get("/emergency-access", response_model=list[EmergencyAccess])
def emergency_access(org_id: OrgId) -> list[EmergencyAccess]:
    """The platform's emergency access to this organisation, newest first, with reasons."""
    return get_emergency_access().for_organisation(org_id)


@router.post("/emergency-access/{grant_id}/end", response_model=EmergencyAccess)
def end_emergency_access(
    grant_id: str, org_id: OrgId, log: Log, me: SignedIn, request: Request
) -> EmergencyAccess:
    """End the platform's access to this organisation now."""
    store = get_emergency_access()
    grant = next((g for g in store.for_organisation(org_id) if g.id == grant_id), None)
    if grant is None:
        raise HTTPException(status_code=404, detail=f"No emergency access {grant_id}")
    audit_note(request, emergency_access=grant_id)
    return store.end(grant_id, me.username)
