"""User accounts, saved to a JSON file readable only by its owner.

Passwords are stored as salted scrypt hashes. Manage accounts with `python -m app.users`.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
from collections.abc import Iterable
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from threading import Lock

from app.models import AccessScope, MIN_PASSWORD_LENGTH, Role, User

DEFAULT_USERS_FILE = Path(__file__).resolve().parents[2] / "users.json"

# scrypt cost: about 50 ms per hash, so guessing passwords offline is slow
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    actual = hashlib.scrypt(
        password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p)
    )
    return hmac.compare_digest(actual, base64.b64decode(digest))


# Checked when the username doesn't exist, so a wrong name takes as long as a wrong password
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def check_password_strength(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Passwords need at least {MIN_PASSWORD_LENGTH} characters")
    if password.lower() == password or password.upper() == password or password.isalpha():
        raise ValueError("Use upper- and lower-case letters and at least one digit or symbol")


class UserStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._users: dict[str, User] = {}
        self._loaded_mtime: float | None = None
        self._lock = Lock()
        self._reload_if_changed()

    def _reload_if_changed(self) -> None:
        """Pick up accounts changed by `python -m app.users` while the server runs."""
        if self.path is None or not self.path.exists():
            return
        mtime = self.path.stat().st_mtime
        if mtime != self._loaded_mtime:
            data = json.loads(self.path.read_text())
            self._users = {u["username"]: User.model_validate(u) for u in data["users"]}
            self._loaded_mtime = mtime

    def get(self, username: str) -> User | None:
        self._reload_if_changed()
        return self._users.get(username.strip().lower())

    def list(self) -> list[User]:
        self._reload_if_changed()
        return sorted(self._users.values(), key=lambda u: u.username)

    def authenticate(self, username: str, password: str) -> User | None:
        """The active user with this password, or None. Takes the same time either way."""
        user = self.get(username)
        valid = verify_password(password, user.password_hash if user else _DUMMY_HASH)
        return user if valid and user is not None and user.active else None

    def add(
        self,
        username: str,
        display_name: str,
        role: Role,
        password: str,
        organisation_id: str | None = None,
    ) -> User:
        check_password_strength(password)
        now = datetime.now(UTC)
        user = User(
            username=username,
            display_name=display_name,
            role=role,
            password_hash=hash_password(password),
            created_at=now,
            password_changed_at=now,
            organisation_id=organisation_id,
        )
        with self._lock:
            if user.username in self._users:
                # Usernames are unique across organisations; don't say whose it is
                raise ValueError(f"The username {user.username} is taken; choose another")
            self._users[user.username] = user
            self._save()
        return user

    def update(
        self,
        username: str,
        *,
        password: str | None = None,
        role: Role | None = None,
        active: bool | None = None,
        display_name: str | None = None,
        organisation_id: str | None = None,
        scope: AccessScope | None = None,
        sso_id: str | None = None,
        break_glass: bool | None = None,
    ) -> User:
        changes: dict = {}
        if sso_id is not None:
            changes["sso_id"] = sso_id.lower() or None  # "" clears it
        if break_glass is not None:
            changes["break_glass"] = break_glass
        if scope is not None:
            changes["scope"] = scope
        if organisation_id is not None:
            changes["organisation_id"] = organisation_id
        if display_name is not None:
            changes["display_name"] = display_name
        if password is not None:
            check_password_strength(password)
            changes |= {
                "password_hash": hash_password(password),
                "password_changed_at": datetime.now(UTC),
            }
        if role is not None:
            changes["role"] = role
        if active is not None:
            changes["active"] = active
        with self._lock:
            user = self.get(username)
            if user is None:
                raise LookupError(f"No user {username}")
            user = user.model_copy(update=changes)
            self._users[user.username] = user
            self._save()
        return user

    def by_sso_id(self, organisation_id: str, sso_id: str) -> User | None:
        """The organisation's account linked to this identity-provider ID."""
        wanted = sso_id.strip().lower()
        return next(
            (u for u in self.list() if u.organisation_id == organisation_id and u.sso_id == wanted),
            None,
        )

    def remove(self, usernames: Iterable[str]) -> None:
        """Delete these accounts (their organisation was deleted)."""
        with self._lock:
            for username in usernames:
                self._users.pop(username, None)
            self._save()

    def _save(self) -> None:
        """Write all users atomically, readable only by this account. Caller holds the lock."""
        if self.path is None:
            return
        payload = {"users": [u.model_dump(mode="json") for u in self._users.values()]}
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(payload, indent=2))
        tmp.replace(self.path)
        self._loaded_mtime = self.path.stat().st_mtime


@lru_cache(maxsize=1)
def get_user_store() -> UserStore:
    """Process-wide accounts saved to RCM_USERS_FILE."""
    return UserStore(Path(os.environ.get("RCM_USERS_FILE", DEFAULT_USERS_FILE)))
