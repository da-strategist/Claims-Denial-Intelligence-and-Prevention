"""Staff administration: member accounts and plan assignment (admins only)."""

import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Path as PathParam
from pydantic import BaseModel, Field

from ..auth.sessions import Permission, require, sessions
from ..auth.users import Role, User, user_store
from ..models.common import DocumentId
from ..services import registry

router = APIRouter(prefix="/api/admin", tags=["admin"])

_admin = require(Permission.MANAGE_USERS)
UsernameParam = PathParam(min_length=3, max_length=254)


class NewUser(BaseModel):
    username: str = Field(min_length=3, max_length=254)
    role: Role = Role.MEMBER
    plan_ids: list[DocumentId] = Field(default_factory=list, max_length=50)


class UserChanges(BaseModel):
    plan_ids: list[DocumentId] | None = Field(None, max_length=50)
    disabled: bool | None = None


def _check_staff_plans(plan_ids: list[str]) -> None:
    """Members can only be assigned staff plans that exist (not someone's
    private upload)."""
    staff_plans = {e["document_id"] for e in registry.load() if e.get("owner") is None}
    unknown = sorted(set(plan_ids) - staff_plans)
    if unknown:
        raise HTTPException(400, f"Unknown plan(s): {', '.join(unknown)}")


def _get(username: str) -> User:
    user = user_store.get(username)
    if user is None:
        raise HTTPException(404, "User not found")
    return user


@router.get("/users")
async def list_users(_: User = Depends(_admin)) -> list[dict]:
    return [u.public() for u in user_store.all()]


@router.post("/users")
async def create_user(body: NewUser, _: User = Depends(_admin)) -> dict:
    """Create an account with a temporary password (returned once; the user
    must change it at first sign-in)."""
    _check_staff_plans(body.plan_ids)
    temporary = secrets.token_urlsafe(12)
    try:
        user = user_store.create(body.username, temporary, body.role, body.plan_ids)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {**user.public(), "temporary_password": temporary}


@router.patch("/users/{username}")
async def update_user(body: UserChanges, username: str = UsernameParam,
                      admin: User = Depends(_admin)) -> dict:
    user = _get(username)
    changes = {}
    if body.plan_ids is not None:
        _check_staff_plans(body.plan_ids)
        changes["plan_ids"] = body.plan_ids
    if body.disabled is not None:
        if user.username == admin.username and body.disabled:
            raise HTTPException(400, "You cannot disable your own account")
        changes["disabled"] = body.disabled
    updated = user_store.update(user.username, **changes)
    if updated.disabled:
        sessions.end_all_for(updated.username)
    return updated.public()


@router.post("/users/{username}/reset-password")
async def reset_password(username: str = UsernameParam, _: User = Depends(_admin)) -> dict:
    """New temporary password (returned once); signs the user out everywhere."""
    user = _get(username)
    temporary = secrets.token_urlsafe(12)
    user_store.update(user.username, password=temporary, must_change_password=True)
    sessions.end_all_for(user.username)
    return {"username": user.username, "temporary_password": temporary}
