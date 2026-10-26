"""Individuals share their own policy documents with a provider, and revoke."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import Path as PathParam
from pydantic import BaseModel

from ..audit import audit_document
from ..auth.sessions import Permission, require
from ..auth.users import User
from ..models.common import DocumentId, DOCUMENT_ID_PATTERN
from ..services import records, registry, sharing

router = APIRouter(prefix="/api/shares", tags=["shares"])

_share = require(Permission.SHARE_POLICIES)


class NewShare(BaseModel):
    document_id: DocumentId
    org_id: DocumentId


def _own_document_or_404(user: User, document_id: str) -> dict:
    for e in registry.load():
        if e["document_id"] == document_id and e.get("owner") == user.username:
            return e
    raise HTTPException(404, "Document not found")


@router.get("/hospitals")
async def hospital_directory(_: User = Depends(_share)) -> list[dict]:
    """Approved providers an individual can share with: name, category and
    location, so similar names can be told apart. Pending sign-ups are not
    listed."""
    return [{"org_id": o.org_id, "name": o.name, "category": o.category,
             "category_label": records.PROVIDER_CATEGORIES.get(o.category, o.category),
             "city": o.city, "address": o.address}
            for o in sorted(records.orgs.all(), key=lambda o: o.name.lower()) if o.usable]


@router.get("")
async def my_shares(user: User = Depends(_share)) -> list[dict]:
    names = {o.org_id: o.name for o in records.orgs.all()}
    return [{"share_id": s.share_id, "document_id": s.document_id, "org_id": s.org_id,
             "org_name": names.get(s.org_id), "created_at": s.created_at}
            for s in records.shares.all() if s.shared_by == user.username]


@router.post("")
async def share(body: NewShare, request: Request, user: User = Depends(_share)) -> dict:
    """Let a provider see one of your documents (until you stop sharing)."""
    _own_document_or_404(user, body.document_id)
    org = records.orgs.get(body.org_id)
    if org is None or not org.usable:
        raise HTTPException(404, "Provider not found")
    audit_document(request, body.document_id)
    for s in records.shares.all():
        if (s.shared_by, s.document_id, s.org_id) == (user.username, body.document_id, body.org_id):
            return {"share_id": s.share_id, "org_name": org.name}  # already shared
    # the provider gets (or already has) a patient record for this person,
    # and the policy is filed under it
    patient = sharing.patient_record_for(user.username, org)
    s = records.shares.add(records.Share(records.new_id(), body.document_id, body.org_id,
                                         user.username, patient.patient_id))
    return {"share_id": s.share_id, "org_name": org.name}


@router.delete("/{share_id}")
async def unshare(request: Request, share_id: str = PathParam(pattern=DOCUMENT_ID_PATTERN),
                  user: User = Depends(_share)) -> dict:
    """Stop sharing: the provider loses access immediately."""
    s = records.shares.get(share_id)
    if s is None or s.shared_by != user.username:
        raise HTTPException(404, "Share not found")
    audit_document(request, s.document_id)
    records.shares.remove(share_id)
    return {"revoked": share_id}
