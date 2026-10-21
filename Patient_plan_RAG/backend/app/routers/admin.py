"""Platform administration: provider organisations and all accounts.

Providers join two ways: they sign themselves up (pending until the platform
admin approves or rejects them), or the platform admin creates one with its
first provider admin (active at once). The platform admin can disable
accounts or reset passwords, and delete spam accounts and rejected
sign-ups. It never sees anyone's policy documents, and it views provider
details but never edits them: the provider's own admin does that.
"""

import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import Path as PathParam
from pydantic import BaseModel, Field

from ..audit import audit_target
from ..auth.sessions import Permission, require, sessions
from ..auth.users import Role, User, user_store
from ..models.common import DOCUMENT_ID_PATTERN
from ..services import accounts, records, registry

router = APIRouter(prefix="/api/admin", tags=["admin"])

_orgs = require(Permission.MANAGE_ORGS)
_users = require(Permission.MANAGE_USERS)
UsernameParam = PathParam(min_length=3, max_length=254)
OrgIdParam = PathParam(pattern=DOCUMENT_ID_PATTERN)


class NewOrg(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    admin_username: str = Field(min_length=3, max_length=254)
    category: str = Field("hospital", max_length=40)
    city: str = Field("", max_length=100)


class Review(BaseModel):
    note: str = Field("", max_length=500)


class OrgChanges(BaseModel):
    """Access only: provider-entered details are not editable here."""
    disabled: bool | None = None


class ConfirmDelete(BaseModel):
    confirm: str = Field(min_length=1, max_length=254)


class UserChanges(BaseModel):
    disabled: bool | None = None


def _org_or_404(org_id: str) -> records.Org:
    org = records.orgs.get(org_id)
    if org is None:
        raise HTTPException(404, "Organisation not found")
    return org


def _org_summary(org: records.Org) -> dict:
    staff = [u for u in user_store.all() if u.org_id == org.org_id]
    signer = user_store.get(org.signed_up_by) if org.signed_up_by else None
    return {"org_id": org.org_id, "name": org.name, "disabled": org.disabled,
            "category": org.category, "status": org.status, "npi": org.npi,
            "address": org.address, "city": org.city, "phone": org.phone,
            "contact_email": org.contact_email, "created_at": org.created_at,
            "signed_up_by": org.signed_up_by,
            "signed_up_by_name": signer.full_name if signer else "",
            "reviewed_by": org.reviewed_by, "reviewed_at": org.reviewed_at,
            "review_note": org.review_note,
            "staff_count": len(staff),
            "patient_count": sum(1 for p in records.patients.all() if p.org_id == org.org_id)}


# ── Provider organisations ───────────────────────────────────────────

@router.get("/orgs")
async def list_orgs(_: User = Depends(_orgs)) -> list[dict]:
    """All providers; pending sign-ups first (oldest first), then by name."""
    pending = sorted((o for o in records.orgs.all() if o.status == records.PENDING),
                     key=lambda o: o.created_at)
    rest = sorted((o for o in records.orgs.all() if o.status != records.PENDING),
                  key=lambda o: o.name.lower())
    return [_org_summary(o) for o in pending + rest]


@router.post("/orgs")
async def create_org(body: NewOrg, request: Request, _: User = Depends(_orgs)) -> dict:
    """Create a provider (active at once) and its first provider admin. The
    admin's temporary password is returned once; they must change it at
    first sign-in."""
    username = body.admin_username.strip().lower()
    audit_target(request, username)
    if body.category not in records.PROVIDER_CATEGORIES:
        raise HTTPException(400, "Choose a provider category.")
    if user_store.get(username):
        raise HTTPException(400, f"An account for {username} already exists.")
    org = records.orgs.add(records.Org(records.new_id(), body.name.strip(),
                                       category=body.category, city=body.city.strip(),
                                       contact_email=username))
    temporary = secrets.token_urlsafe(12)
    try:
        user_store.create(username, temporary, Role.HOSPITAL_ADMIN, org_id=org.org_id)
    except ValueError as exc:
        records.orgs.remove(org.org_id)
        raise HTTPException(400, str(exc)) from exc
    return {**_org_summary(org), "admin_username": username, "temporary_password": temporary}


@router.get("/orgs/{org_id}")
async def org_detail(org_id: str = OrgIdParam, _: User = Depends(_orgs)) -> dict:
    """A provider's details as it entered them (read-only here) and its
    staff accounts."""
    org = _org_or_404(org_id)
    staff = [{k: v for k, v in u.public().items() if k not in ("org_id", "phone")}
             for u in user_store.all() if u.org_id == org_id]
    return {**_org_summary(org),
            "category_label": records.PROVIDER_CATEGORIES.get(org.category, org.category),
            "staff": staff,
            "connection_count": sum(1 for p in records.providers.all() if p.org_id == org_id),
            "share_count": sum(1 for s in records.shares.all() if s.org_id == org_id)}


@router.delete("/orgs/{org_id}")
async def delete_org(body: ConfirmDelete, org_id: str = OrgIdParam,
                     _: User = Depends(_orgs)) -> dict:
    """Delete a rejected provider sign-up and its accounts. Approved
    providers hold patient records: disable them instead."""
    from . import policies

    org = _org_or_404(org_id)
    if org.status != records.REJECTED:
        raise HTTPException(400, "Only rejected sign-ups can be deleted. Reject a pending sign-up "
                                 "first; disable an approved provider instead.")
    if body.confirm.strip() != org.name:
        raise HTTPException(400, "Type the provider's name exactly to confirm")
    accounts.delete_org(org_id, policies.CHUNK_DIR, policies.UPLOAD_DIR)
    return {"deleted": org_id}


@router.patch("/orgs/{org_id}")
async def update_org(body: OrgChanges, org_id: str = OrgIdParam, _: User = Depends(_orgs)) -> dict:
    """Disable or re-enable a provider; disabling signs out all its staff."""
    _org_or_404(org_id)
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    org = records.orgs.update(org_id, **changes)
    if org.disabled:
        _sign_out_staff(org_id)
    return _org_summary(org)


def _sign_out_staff(org_id: str) -> None:
    for u in user_store.all():
        if u.org_id == org_id:
            sessions.end_all_for(u.username)


def _review(org_id: str, status: str, note: str, admin: User) -> records.Org:
    return records.orgs.update(org_id, status=status, review_note=note.strip(),
                               reviewed_by=admin.username,
                               reviewed_at=datetime.now(UTC).isoformat())


@router.post("/orgs/{org_id}/approve")
async def approve_org(body: Review, org_id: str = OrgIdParam,
                      admin: User = Depends(_orgs)) -> dict:
    """Approve a provider sign-up (or reverse a rejection): its staff can
    work, and individuals can find it and share with it."""
    if _org_or_404(org_id).status == records.ACTIVE:
        raise HTTPException(400, "This provider is already approved.")
    return _org_summary(_review(org_id, records.ACTIVE, body.note, admin))


@router.post("/orgs/{org_id}/reject")
async def reject_org(body: Review, org_id: str = OrgIdParam,
                     admin: User = Depends(_orgs)) -> dict:
    """Reject a pending provider sign-up: its admin can no longer sign in and
    is shown the note. Approved providers are disabled instead."""
    if _org_or_404(org_id).status != records.PENDING:
        raise HTTPException(400, "Only pending sign-ups can be rejected; disable an approved provider instead.")
    org = _review(org_id, records.REJECTED, body.note, admin)
    _sign_out_staff(org_id)
    return _org_summary(org)


# ── Accounts ─────────────────────────────────────────────────────────

def _user_or_404(username: str) -> User:
    user = user_store.get(username)
    if user is None:
        raise HTTPException(404, "User not found")
    return user


def _user_summary(u: User, orgs: dict[str, records.Org]) -> dict:
    org = orgs.get(u.org_id)
    return {**u.public(), "org_name": org.name if org else None,
            "org_status": org.status if org else None}


@router.get("/users")
async def list_users(_: User = Depends(_users)) -> list[dict]:
    orgs = {o.org_id: o for o in records.orgs.all()}
    return [_user_summary(u, orgs) for u in user_store.all()]


@router.get("/users/{username}")
async def user_detail(username: str = UsernameParam, _: User = Depends(_users)) -> dict:
    """One account, with counts of what it holds (never document names or
    contents: the platform admin sees no one's policies)."""
    user = _user_or_404(username)
    detail = _user_summary(user, {o.org_id: o for o in records.orgs.all()})
    if user.role is Role.INDIVIDUAL:
        detail["holds"] = {
            "policies": sum(1 for e in registry.load() if e.get("owner") == user.username),
            "shares": sum(1 for s in records.shares.all() if s.shared_by == user.username),
            "providers": sum(1 for p in records.providers.all() if p.owner == user.username),
            "connected_providers": sum(1 for p in records.providers.all()
                                       if p.owner == user.username and p.org_id),
        }
    return detail


@router.delete("/users/{username}")
async def delete_user(body: ConfirmDelete, username: str = UsernameParam,
                      admin: User = Depends(_users)) -> dict:
    """Delete an individual's account (e.g. spam) with everything it holds.
    Provider staff are removed by their provider admin; platform admins
    can't be deleted here."""
    from . import policies  # paths are read at call time so tests can redirect them

    user = _user_or_404(username)
    if user.role is not Role.INDIVIDUAL:
        raise HTTPException(400, "Only individual accounts can be deleted here. Provider staff are "
                                 "managed by their provider admin; delete a rejected provider instead.")
    if body.confirm.strip().lower() != user.username:
        raise HTTPException(400, "Type the account's email address exactly to confirm")
    accounts.delete_individual(user.username, policies.CHUNK_DIR, policies.UPLOAD_DIR)
    return {"deleted": user.username}


@router.patch("/users/{username}")
async def update_user(body: UserChanges, username: str = UsernameParam,
                      admin: User = Depends(_users)) -> dict:
    user = _user_or_404(username)
    if body.disabled is None:
        return user.public()
    if user.username == admin.username and body.disabled:
        raise HTTPException(400, "You cannot disable your own account")
    updated = user_store.update(user.username, disabled=body.disabled)
    if updated.disabled:
        sessions.end_all_for(updated.username)
    return updated.public()


@router.post("/users/{username}/reset-password")
async def reset_password(username: str = UsernameParam, _: User = Depends(_users)) -> dict:
    """New temporary password (returned once); signs the user out everywhere."""
    user = _user_or_404(username)
    temporary = secrets.token_urlsafe(12)
    user_store.update(user.username, password=temporary, must_change_password=True)
    sessions.end_all_for(user.username)
    return {"username": user.username, "temporary_password": temporary}
