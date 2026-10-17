"""User accounts, managed by administrators from the Users page.

Administrators see and manage only their own organisation's accounts: another
organisation's username is "not found", the same as one that doesn't exist.

Safeguards: administrators can't change their own role or disable themselves, and the
last active administrator can't be demoted or disabled, so the app always has someone
who can manage it. Disabling an account or resetting its password signs that person out.
Every change is in the audit log (never the password).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.data.scoped import ScopedClaims
from app.data.users import UserStore, get_user_store
from app.models import (
    ORGANISATION_ROLES,
    AccessScope,
    PasswordReset,
    Permission,
    Role,
    User,
    UserCreate,
    UserSummary,
    UserUpdate,
)
from app.models.auth import Username
from app.services.auth import SessionStore, SignedIn, audit_note, get_session_store, require
from app.services.org_context import OrgClaims, OrgId

router = APIRouter(
    prefix="/api/users", tags=["users"], dependencies=[require(Permission.USERS_MANAGE)]
)

Users = Annotated[UserStore, Depends(get_user_store)]
Sessions = Annotated[SessionStore, Depends(get_session_store)]


def _summary(user: User) -> UserSummary:
    return UserSummary.model_validate(user.model_dump())


def _target(users: UserStore, username: str, org_id: str) -> User:
    user = users.get(username)
    if user is None or user.organisation_id != org_id:
        raise HTTPException(status_code=404, detail=f"No user {username}")
    return user


@router.get("", response_model=list[UserSummary])
def list_users(users: Users, org_id: OrgId) -> list[UserSummary]:
    """Every account in the organisation, active and disabled."""
    return [_summary(user) for user in users.list() if user.organisation_id == org_id]


@router.post("", response_model=UserSummary, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, users: Users, request: Request, org_id: OrgId) -> UserSummary:
    """Add an account. The password must meet the policy (12+ characters, mixed case,
    and a digit or symbol)."""
    audit_note(request, new_user=body.username, role=body.role)
    _organisation_role(body.role)
    try:
        # Into the administrator's own organisation; the body can't choose another
        user = users.add(body.username, body.display_name, body.role, body.password, org_id)
    except ValueError as err:
        code = 409 if "is taken" in str(err) else 422
        raise HTTPException(status_code=code, detail=str(err)) from err
    return _summary(user)


@router.patch("/{username}", response_model=UserSummary)
def update_user(
    username: Username,
    body: UserUpdate,
    users: Users,
    sessions: Sessions,
    me: SignedIn,
    request: Request,
    org_id: OrgId,
    claims: OrgClaims,
) -> UserSummary:
    """Rename, change role, limit what the account sees (`scope`), or disable / enable it."""
    target = _target(users, username, org_id)
    if body.role is not None:
        _organisation_role(body.role)
    is_me = target.username == me.username
    if is_me and body.role is not None and body.role != target.role:
        raise HTTPException(
            status_code=422,
            detail="You can't change your own role; ask another administrator",
        )
    if is_me and body.active is False:
        raise HTTPException(
            status_code=422, detail="You can't disable your own account"
        )
    losing_admin = target.role == Role.ADMIN and target.active and (
        (body.role is not None and body.role != Role.ADMIN) or body.active is False
    )
    if losing_admin and _active_admins(users, org_id) == 1:
        raise HTTPException(
            status_code=409,
            detail=f"{target.username} is the only active administrator; make someone else an administrator first",
        )

    new_role = body.role or target.role
    if body.scope is not None and body.scope.restricted:
        if new_role == Role.ADMIN:
            raise HTTPException(
                status_code=422, detail="Administrators always see the whole organisation"
            )
        _check_scope_ids(body.scope, claims)

    changes = body.model_dump(exclude_none=True, exclude={"scope"})
    if body.scope is not None:
        changes["scope"] = body.scope
    elif new_role == Role.ADMIN and target.scope.restricted:
        changes["scope"] = AccessScope()  # promoted: the old limits no longer apply
    audit_note(request, **body.model_dump(exclude_none=True, mode="json"))
    user = users.update(target.username, **changes)
    if body.active is False:
        sessions.end_all(user.username)
    return _summary(user)


@router.post("/{username}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    username: Username,
    body: PasswordReset,
    users: Users,
    sessions: Sessions,
    me: SignedIn,
    request: Request,
    org_id: OrgId,
) -> None:
    """Set a new password. Anyone else is signed out and signs in with the new one."""
    target = _target(users, username, org_id)
    audit_note(request, password_reset=True)
    try:
        users.update(target.username, password=body.password)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    if target.username != me.username:
        sessions.end_all(target.username)


def _organisation_role(role: Role) -> None:
    if role not in ORGANISATION_ROLES:
        raise HTTPException(status_code=422, detail="Organisations can only give analyst, biller, or admin roles")


def _check_scope_ids(scope: AccessScope, claims: ScopedClaims) -> None:
    """Every limit must be one of the organisation's own facilities, departments, providers."""
    known = {
        "facilities": {f.facility_id for f in claims.list_facilities()},
        "departments": {d.department_id for d in claims.list_departments()},
        "providers": {p.provider_id for p in claims.list_providers()},
    }
    for kind, ids in known.items():
        unknown = [i for i in getattr(scope, kind) if i not in ids]
        if unknown:
            raise HTTPException(status_code=422, detail=f"Unknown {kind}: {', '.join(unknown)}")


def _active_admins(users: UserStore, org_id: str) -> int:
    return sum(
        1
        for user in users.list()
        if user.organisation_id == org_id and user.role == Role.ADMIN and user.active
    )
