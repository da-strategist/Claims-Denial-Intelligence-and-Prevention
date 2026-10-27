"""Sign-in sessions and the permission checks every route depends on.

A session is a random token in an HttpOnly, SameSite=Strict cookie; the server keeps only
its SHA-256. Sessions end after RCM_SESSION_IDLE_MINUTES without a request (HIPAA automatic
logoff) or RCM_SESSION_MAX_HOURS in total, at sign-out, or when the user is deactivated.
They live in memory, so restarting the API signs everyone out, unless RCM_SESSIONS_FILE
names a file to keep them in (for a demo host that stops and starts on its own; refused in
production). The file holds only the digests, never a usable token.
"""

import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.data.emergency import get_emergency_access
from app.data.orgs import OrgStatus, get_org_registry
from app.data.secure_files import production
from app.data.users import UserStore, get_user_store
from app.models import Permission, Role, User

SESSION_COOKIE = "rcm_session"
MAX_FAILED_LOGINS = 5
LOCKOUT = timedelta(minutes=15)
# A kept session's last request is saved at most this often (it's checked against the idle limit)
SAVE_SEEN_EVERY = timedelta(seconds=60)

PERMISSION_LABELS = {
    Permission.CLAIMS_READ: "view claims",
    Permission.PATIENTS_READ: "view patient details",
    Permission.CLAIMS_WRITE: "change claims",
    Permission.RULES_WRITE: "change validation rules",
    Permission.AUDIT_READ: "read the audit log",
    Permission.USERS_MANAGE: "manage user accounts",
    Permission.DATA_EXPORT: "export the organisation's data",
    Permission.PLATFORM_MANAGE: "manage the platform",
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
    def __init__(self, idle: timedelta, max_age: timedelta, path: Path | None = None) -> None:
        self.idle, self.max_age = idle, max_age
        self.path = path
        self._sessions: dict[str, Session] = {}
        self._saved_seen: dict[str, datetime] = {}
        self._lock = Lock()
        if path is not None and path.exists():
            now = _now()
            for key, item in json.loads(path.read_text()).items():
                session = Session(
                    item["username"],
                    datetime.fromisoformat(item["created_at"]),
                    datetime.fromisoformat(item["last_seen"]),
                )
                if not self._expired(session, now):
                    self._sessions[key] = session
                    self._saved_seen[key] = session.last_seen

    def _expired(self, session: Session, now: datetime) -> bool:
        return now - session.last_seen > self.idle or now - session.created_at > self.max_age

    def _save(self) -> None:
        """Write the sessions to the file, owner-only and atomically. Caller holds the lock."""
        if self.path is None:
            return
        payload = {
            key: {
                "username": s.username,
                "created_at": s.created_at.isoformat(),
                "last_seen": s.last_seen.isoformat(),
            }
            for key, s in self._sessions.items()
        }
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload))
        temp.chmod(0o600)
        temp.replace(self.path)
        self._saved_seen = {key: s.last_seen for key, s in self._sessions.items()}

    def create(self, username: str) -> str:
        """Start a session; returns the token for the cookie."""
        token = secrets.token_urlsafe(32)
        now = _now()
        with self._lock:
            self._sessions[_digest(token)] = Session(username, now, now)
            self._save()
        return token

    def touch(self, token: str) -> Session | None:
        """The live session for a token, marking it used now; expired sessions are dropped."""
        key, now = _digest(token), _now()
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                return None
            if self._expired(session, now):
                del self._sessions[key]
                self._save()
                return None
            session.last_seen = now
            if self.path is not None and now - self._saved_seen.get(key, now) >= SAVE_SEEN_EVERY:
                self._save()
            return session

    def end(self, token: str) -> None:
        with self._lock:
            self._sessions.pop(_digest(token), None)
            self._save()

    def end_all(self, username: str) -> None:
        with self._lock:
            self._sessions = {k: s for k, s in self._sessions.items() if s.username != username}
            self._save()

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
    path = os.environ.get("RCM_SESSIONS_FILE", "").strip()
    if path and production():
        raise RuntimeError("RCM_SESSIONS_FILE keeps sessions across restarts: not in production")
    return SessionStore(
        idle=timedelta(minutes=float(os.environ.get("RCM_SESSION_IDLE_MINUTES", 15))),
        max_age=timedelta(hours=float(os.environ.get("RCM_SESSION_MAX_HOURS", 8))),
        path=Path(path) if path else None,
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
    if user is not None and user.role == Role.PLATFORM:
        user = with_emergency_access(user)
    # An account without a working organisation reaches no data at all (fail closed)
    if user is None or not user.active or organisation_problem(user):
        if token:
            sessions.end(token)
        raise HTTPException(status_code=401, detail="Sign in to continue")
    request.state.user = user
    request.state.session = session
    return user


SignedIn = Annotated[User, Depends(current_user)]


def with_emergency_access(user: User) -> User:
    """A platform account, as an organisation's read-only user while it has emergency
    access to it (this request only; nothing is stored on the account)."""
    grant = get_emergency_access().active_for(user.username)
    org = get_org_registry().get(grant.organisation_id) if grant else None
    if grant is None or org is None or org.status != OrgStatus.ACTIVE:
        return user
    return user.model_copy(
        update={"organisation_id": grant.organisation_id, "emergency_access_id": grant.id}
    )


def organisation_problem(user: User) -> str | None:
    """Why this account can't reach its organisation's data, or None if it can. Platform
    accounts belong to no organisation and only reach one through emergency access."""
    if user.role == Role.PLATFORM and user.emergency_access_id is None:
        return None
    if user.organisation_id is None:
        return "Your account isn't set up for an organisation yet. Ask an administrator."
    org = get_org_registry().get(user.organisation_id)
    if org is None:
        return "Your account's organisation no longer exists. Ask an administrator."
    if org.status == OrgStatus.DELETED:
        return "Your account's organisation no longer exists. Ask an administrator."
    if org.status != OrgStatus.ACTIVE:
        return "Your organisation's access is suspended."
    if org.baa is None and production():
        # No real patient data without a signed business associate agreement
        return "Your organisation's business associate agreement isn't on record yet."
    return None


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
