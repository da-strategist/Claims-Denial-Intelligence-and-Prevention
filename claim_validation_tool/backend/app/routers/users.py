"""User accounts, managed by administrators from the Users page.

Safeguards: administrators can't change their own role or disable themselves, and the
last active administrator can't be demoted or disabled, so the app always has someone
who can manage it. Disabling an account or resetting its password signs that person out.
Every change is in the audit log (never the password).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.data.users import UserStore, get_user_store
from app.models import (
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

router = APIRouter(
    prefix="/api/users", tags=["users"], dependencies=[require(Permission.USERS_MANAGE)]
)

Users = Annotated[UserStore, Depends(get_user_store)]
Sessions = Annotated[SessionStore, Depends(get_session_store)]


def _summary(user: User) -> UserSummary:
    return UserSummary.model_validate(user.model_dump())


def _target(users: UserStore, username: str) -> User:
    user = users.get(username)
    if user is None:
        raise HTTPException(status_code=404, detail=f"No user {username}")
    return user


@router.get("", response_model=list[UserSummary])
def list_users(users: Users) -> list[UserSummary]:
    """Every account, active and disabled."""
    return [_summary(user) for user in users.list()]


@router.post("", response_model=UserSummary, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, users: Users, request: Request) -> UserSummary:
    """Add an account. The password must meet the policy (12+ characters, mixed case,
    and a digit or symbol)."""
    audit_note(request, new_user=body.username, role=body.role)
    try:
        user = users.add(body.username, body.display_name, body.role, body.password)
    except ValueError as err:
        code = 409 if "already exists" in str(err) else 422
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
) -> UserSummary:
    """Rename, change role, or disable / enable an account."""
    target = _target(users, username)
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
    if losing_admin and _active_admins(users) == 1:
        raise HTTPException(
            status_code=409,
            detail=f"{target.username} is the only active administrator; make someone else an administrator first",
        )

    changes = body.model_dump(exclude_none=True)
    audit_note(request, **changes)
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
) -> None:
    """Set a new password. Anyone else is signed out and signs in with the new one."""
    target = _target(users, username)
    audit_note(request, password_reset=True)
    try:
        users.update(target.username, password=body.password)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    if target.username != me.username:
        sessions.end_all(target.username)


def _active_admins(users: UserStore) -> int:
    return sum(1 for user in users.list() if user.role == Role.ADMIN and user.active)
