"""Read the audit log (admins only). Reading it is itself recorded."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.models import AuditEvent, AuditQuery, AuditVerification, Permission
from app.services.auth import require
from app.services.org_context import OrgAudit

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
