"""Sign-in sessions and the permission checks every route depends on.

A session is a random token in an HttpOnly, SameSite=Strict cookie; the server keeps only
its SHA-256. Sessions end after RCM_SESSION_IDLE_MINUTES without a request (HIPAA automatic
logoff) or RCM_SESSION_MAX_HOURS in total, at sign-out, or when the user is deactivated.
They live in memory, so restarting the API signs everyone out.
"""

import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from threading import Lock
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.data.users import UserStore, get_user_store
from app.models import Permission, User

SESSION_COOKIE = "rcm_session"
MAX_FAILED_LOGINS = 5
LOCKOUT = timedelta(minutes=15)

PERMISSION_LABELS = {
    Permission.CLAIMS_READ: "view claims",
    Permission.PATIENTS_READ: "view patient details",
    Permission.CLAIMS_WRITE: "change claims",
    Permission.RULES_WRITE: "change validation rules",
    Permission.AUDIT_READ: "read the audit log",
    Permission.USERS_MANAGE: "manage user accounts",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class Session:
    username: str
    created_at: datetime
    last_seen: datetime


class SessionStore:
    def __init__(self, idle: timedelta, max_age: timedelta) -> None:
        self.idle, self.max_age = idle, max_age
        self._sessions: dict[str, Session] = {}
        self._lock = Lock()

    def create(self, username: str) -> str:
        """Start a session; returns the token for the cookie."""
        token = secrets.token_urlsafe(32)
        now = _now()
        with self._lock:
            self._sessions[_digest(token)] = Session(username, now, now)
        return token

    def touch(self, token: str) -> Session | None:
        """The live session for a token, marking it used now; expired sessions are dropped."""
        key, now = _digest(token), _now()
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                return None
            if now - session.last_seen > self.idle or now - session.created_at > self.max_age:
                del self._sessions[key]
                return None
            session.last_seen = now
            return session

    def end(self, token: str) -> None:
        with self._lock:
            self._sessions.pop(_digest(token), None)

    def end_all(self, username: str) -> None:
        with self._lock:
            self._sessions = {k: s for k, s in self._sessions.items() if s.username != username}

    def expires_at(self, session: Session) -> datetime:
        return session.created_at + self.max_age


class LoginThrottle:
    """Locks a username for LOCKOUT after MAX_FAILED_LOGINS failures in a row."""

    def __init__(self) -> None:
        self._failures: dict[str, list[datetime]] = {}
        self._lock = Lock()

    def locked(self, username: str) -> bool:
        with self._lock:
            recent = [t for t in self._failures.get(username, []) if _now() - t < LOCKOUT]
            self._failures[username] = recent
            return len(recent) >= MAX_FAILED_LOGINS

    def failed(self, username: str) -> None:
        with self._lock:
            self._failures.setdefault(username, []).append(_now())

    def succeeded(self, username: str) -> None:
        with self._lock:
            self._failures.pop(username, None)


@lru_cache(maxsize=1)
def get_session_store() -> SessionStore:
    return SessionStore(
        idle=timedelta(minutes=float(os.environ.get("RCM_SESSION_IDLE_MINUTES", 15))),
        max_age=timedelta(hours=float(os.environ.get("RCM_SESSION_MAX_HOURS", 8))),
    )


@lru_cache(maxsize=1)
def get_login_throttle() -> LoginThrottle:
    return LoginThrottle()


def cookie_secure() -> bool:
    """Send the cookie over HTTPS only. Off by default for http://localhost development."""
    return os.environ.get("RCM_COOKIE_SECURE", "").lower() in ("1", "true", "yes")


# --- Route dependencies -----------------------------------------------------------------


def current_user(
    request: Request,
    sessions: Annotated[SessionStore, Depends(get_session_store)],
    users: Annotated[UserStore, Depends(get_user_store)],
) -> User:
    """The signed-in, active user. Also noted on the request for the audit log."""
    token = request.cookies.get(SESSION_COOKIE)
    session = sessions.touch(token) if token else None
    user = users.get(session.username) if session else None
    if user is None or not user.active:
        if token:
            sessions.end(token)
        raise HTTPException(status_code=401, detail="Sign in to continue")
    request.state.user = user
    request.state.session = session
    return user


SignedIn = Annotated[User, Depends(current_user)]


def require(permission: Permission):
    """Dependency that refuses (403) users whose role lacks `permission`."""

    def check(user: SignedIn) -> User:
        if not user.can(permission):
            raise HTTPException(
                status_code=403,
                detail=f"Your role ({user.role}) can't {PERMISSION_LABELS[permission]}",
            )
        return user

    return Depends(check)


def audit_note(request: Request, **detail) -> None:
    """Add details (record IDs, what changed) to this request's audit event."""
    request.state.audit = {**getattr(request.state, "audit", {}), **detail}
