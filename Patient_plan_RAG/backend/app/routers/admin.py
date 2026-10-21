"""Platform administration: hospital organisations and all accounts.

The platform admin onboards a hospital (organisation + its first hospital
admin) and can disable accounts or reset passwords. It never sees anyone's
policy documents; the hospital manages its own staff and patients.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import Path as PathParam
from pydantic import BaseModel, Field

from ..audit import audit_target
from ..auth.sessions import Permission, require, sessions
from ..auth.users import Role, User, user_store
from ..models.common import DOCUMENT_ID_PATTERN
from ..services import records

router = APIRouter(prefix="/api/admin", tags=["admin"])

_orgs = require(Permission.MANAGE_ORGS)
_users = require(Permission.MANAGE_USERS)
UsernameParam = PathParam(min_length=3, max_length=254)
OrgIdParam = PathParam(pattern=DOCUMENT_ID_PATTERN)


class NewOrg(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    admin_username: str = Field(min_length=3, max_length=254)


class OrgChanges(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200)
    disabled: bool | None = None


class UserChanges(BaseModel):
    disabled: bool | None = None


def _org_or_404(org_id: str) -> records.Org:
    org = records.orgs.get(org_id)
    if org is None:
        raise HTTPException(404, "Organisation not found")
    return org


def _org_summary(org: records.Org) -> dict:
    staff = [u for u in user_store.all() if u.org_id == org.org_id]
    return {"org_id": org.org_id, "name": org.name, "disabled": org.disabled,
            "city": org.city,
            "staff_count": len(staff),
            "patient_count": sum(1 for p in records.patients.all() if p.org_id == org.org_id)}


# ── Hospital organisations ───────────────────────────────────────────

@router.get("/orgs")
async def list_orgs(_: User = Depends(_orgs)) -> list[dict]:
    return [_org_summary(o) for o in sorted(records.orgs.all(), key=lambda o: o.name.lower())]


@router.post("/orgs")
async def create_org(body: NewOrg, request: Request, _: User = Depends(_orgs)) -> dict:
    """Create a hospital and its first hospital admin. The admin's temporary
    password is returned once; they must change it at first sign-in."""
    username = body.admin_username.strip().lower()
    audit_target(request, username)
    if user_store.get(username):
        raise HTTPException(400, f"An account for {username} already exists.")
    org = records.orgs.add(records.Org(records.new_id(), body.name.strip()))
    temporary = secrets.token_urlsafe(12)
    try:
        user_store.create(username, temporary, Role.HOSPITAL_ADMIN, org_id=org.org_id)
    except ValueError as exc:
        records.orgs.remove(org.org_id)
        raise HTTPException(400, str(exc)) from exc
    return {**_org_summary(org), "admin_username": username, "temporary_password": temporary}


@router.patch("/orgs/{org_id}")
async def update_org(body: OrgChanges, org_id: str = OrgIdParam, _: User = Depends(_orgs)) -> dict:
    """Rename or disable a hospital; disabling signs out all its staff."""
    _org_or_404(org_id)
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    org = records.orgs.update(org_id, **changes)
    if org.disabled:
        for u in user_store.all():
            if u.org_id == org_id:
                sessions.end_all_for(u.username)
    return _org_summary(org)


# ── Accounts ─────────────────────────────────────────────────────────

def _user_or_404(username: str) -> User:
    user = user_store.get(username)
    if user is None:
        raise HTTPException(404, "User not found")
    return user


@router.get("/users")
async def list_users(_: User = Depends(_users)) -> list[dict]:
    names = {o.org_id: o.name for o in records.orgs.all()}
    return [{**u.public(), "org_name": names.get(u.org_id)} for u in user_store.all()]


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
