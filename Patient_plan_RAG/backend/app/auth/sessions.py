"""Sessions, login throttling, identity providers, and route permissions.

A session is a random token in an HttpOnly, SameSite=Strict cookie; the
server keeps only the token's SHA-256 digest. Sessions end after
SESSION_IDLE_MINUTES without use or SESSION_MAX_HOURS after sign-in.
Like the rate limiter, state is in memory: per process, lost on restart.

Every API route except /api/health and sign-in declares a permission with
`Depends(require(Permission.X))`.
"""

import hashlib
import os
import secrets
import time
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from fastapi import Depends, HTTPException, Request

from ..services import records
from .users import Role, User, user_store

SESSION_COOKIE = "ppr_session"
SESSION_IDLE_SECONDS = int(os.getenv("SESSION_IDLE_MINUTES", "30")) * 60
SESSION_MAX_SECONDS = int(os.getenv("SESSION_MAX_HOURS", "12")) * 3600
LOGIN_MAX_FAILURES = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60


def cookie_secure() -> bool:
    """Send the cookie over HTTPS only; set COOKIE_SECURE=false for local http."""
    return os.getenv("COOKIE_SECURE", "false").lower() == "true"


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ── Identity providers ───────────────────────────────────────────────

class IdentityProvider(Protocol):
    """Turns credentials into a known, enabled user (or None).

    Local passwords today; an OIDC provider for the insurer's member portal
    can implement the same role later (it would map ID-token claims to a
    User instead of checking a password).
    """

    def authenticate(self, username: str, password: str) -> User | None: ...


identity_provider: IdentityProvider = user_store


# ── Sessions ─────────────────────────────────────────────────────────

@dataclass
class Session:
    username: str
    created: float
    last_seen: float


class SessionStore:
    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def start(self, username: str) -> str:
        token = secrets.token_urlsafe(32)
        now = time.monotonic()
        self._sessions[_digest(token)] = Session(username, now, now)
        return token

    def touch(self, token: str) -> Session | None:
        key, now = _digest(token), time.monotonic()
        session = self._sessions.get(key)
        if session is None:
            return None
        if now - session.last_seen > SESSION_IDLE_SECONDS or now - session.created > SESSION_MAX_SECONDS:
            del self._sessions[key]
            return None
        session.last_seen = now
        return session

    def end(self, token: str) -> None:
        self._sessions.pop(_digest(token), None)

    def end_all_for(self, username: str) -> None:
        for key in [k for k, s in self._sessions.items() if s.username == username]:
            del self._sessions[key]

    def reset(self) -> None:
        self._sessions.clear()


class LoginThrottle:
    """Lock a username out after repeated failures (per process)."""

    def __init__(self):
        self._failures: dict[str, list[float]] = {}

    def locked_for(self, username: str) -> float:
        now = time.monotonic()
        recent = [t for t in self._failures.get(username, []) if now - t < LOGIN_LOCKOUT_SECONDS]
        self._failures[username] = recent
        if len(recent) >= LOGIN_MAX_FAILURES:
            return LOGIN_LOCKOUT_SECONDS - (now - recent[0])
        return 0.0

    def failed(self, username: str) -> None:
        self._failures.setdefault(username, []).append(time.monotonic())

    def succeeded(self, username: str) -> None:
        self._failures.pop(username, None)

    def reset(self) -> None:
        self._failures.clear()


sessions = SessionStore()
login_throttle = LoginThrottle()


# ── Permissions ──────────────────────────────────────────────────────

class Permission(str, Enum):
    READ_POLICIES = "read_policies"      # view documents you may access (auth/access.py)
    ASK = "ask"                          # chat and coverage questions
    UPLOAD_POLICY = "upload_policy"      # individuals: own; hospitals: to a patient; admin: samples
    VIEW_DASHBOARD = "view_dashboard"
    SHARE_POLICIES = "share_policies"    # individuals share their documents with a hospital
    MANAGE_OWN_DATA = "manage_own_data"  # individuals: providers, export, delete account
    MANAGE_PATIENTS = "manage_patients"  # hospital patient records
    MANAGE_STAFF = "manage_staff"        # hospital admins: their hospital's staff
    MANAGE_ORGS = "manage_orgs"          # platform admin: hospital organisations
    MANAGE_USERS = "manage_users"        # platform admin: all accounts


_COMMON = {Permission.READ_POLICIES, Permission.ASK, Permission.UPLOAD_POLICY,
           Permission.VIEW_DASHBOARD}
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.INDIVIDUAL: _COMMON | {Permission.SHARE_POLICIES, Permission.MANAGE_OWN_DATA},
    Role.HOSPITAL_STAFF: _COMMON | {Permission.MANAGE_PATIENTS},
    Role.HOSPITAL_ADMIN: _COMMON | {Permission.MANAGE_PATIENTS, Permission.MANAGE_STAFF},
    Role.PLATFORM_ADMIN: _COMMON | {Permission.MANAGE_ORGS, Permission.MANAGE_USERS},
}


def current_user(request: Request) -> User:
    """The signed-in user, or 401."""
    token = request.cookies.get(SESSION_COOKIE)
    session = sessions.touch(token) if token else None
    user = user_store.get(session.username) if session else None
    if user is not None and user.org_id:  # a disabled hospital disables its staff
        org = records.orgs.get(user.org_id)
        if org is None or org.disabled:
            user = None
    if user is None or user.disabled:
        if token:
            sessions.end(token)
        raise HTTPException(401, "Sign in required")
    request.state.user = user  # for the audit log
    return user


def signed_in(request: Request) -> User:
    """Signed in, even if a password change is still pending."""
    return current_user(request)


def require(permission: Permission):
    """Dependency: signed in, password changed, and holding `permission`."""

    def check(user: User = Depends(current_user)) -> User:
        if user.must_change_password:
            raise HTTPException(403, "Password change required")
        if permission not in ROLE_PERMISSIONS[user.role]:
            raise HTTPException(403, "Not permitted")
        return user

    return check
