"""User accounts stored in a JSON file, passwords as salted scrypt hashes.

Manage accounts with `python -m backend.app.users`. The file holds password
hashes, so it is gitignored and written with owner-only permissions.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from threading import Lock

BASE_DIR = Path(__file__).resolve().parents[3]
USERS_FILE = Path(os.getenv("USERS_FILE", str(BASE_DIR / "data" / "users.json")))

MIN_PASSWORD_LENGTH = 12
# scrypt cost: tens of milliseconds per hash, so offline guessing is slow
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2 ** 14, 8, 1


class Role(str, Enum):
    INDIVIDUAL = "individual"          # self-registered policyholder: own documents only
    HOSPITAL_STAFF = "hospital_staff"  # sees their hospital's patients + policies shared with it
    HOSPITAL_ADMIN = "hospital_admin"  # hospital staff who also manage that hospital's staff
    PLATFORM_ADMIN = "platform_admin"  # operator: hospitals and accounts, no patient documents


HOSPITAL_ROLES = frozenset({Role.HOSPITAL_STAFF, Role.HOSPITAL_ADMIN})
# Roles stored before Phase F (insurer model)
_LEGACY_ROLES = {"member": Role.INDIVIDUAL, "admin": Role.PLATFORM_ADMIN}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${b64(salt)}${b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt),
                                n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(actual, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


# Verified against when the username is unknown, so a login for a missing
# account costs the same time as a wrong password.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def check_password_policy(password: str) -> str | None:
    """Why a password is unacceptable, or None."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    return None


@dataclass
class User:
    username: str  # email address, lowercased
    role: Role
    password_hash: str = ""
    org_id: str | None = None  # hospital organisation (hospital roles only)
    must_change_password: bool = False
    disabled: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def public(self) -> dict:
        """Safe to return from the API (no password hash)."""
        return {
            "username": self.username,
            "role": self.role.value,
            "org_id": self.org_id,
            "must_change_password": self.must_change_password,
            "disabled": self.disabled,
        }


class UserStore:
    def __init__(self, path: Path = USERS_FILE):
        self.path = path
        self._lock = Lock()

    def _load(self) -> dict[str, User]:
        if not self.path.exists():
            return {}
        known = {f.name for f in fields(User)}
        users = {}
        for raw in json.loads(self.path.read_text()):
            role = _LEGACY_ROLES.get(raw["role"]) or Role(raw["role"])
            kept = {k: v for k, v in raw.items() if k in known}  # drops e.g. old plan_ids
            users[raw["username"]] = User(**{**kept, "role": role})
        return users

    def _save(self, users: dict[str, User]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        data = [{**asdict(u), "role": u.role.value} for u in users.values()]
        tmp.write_text(json.dumps(data, indent=2))
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)

    def get(self, username: str) -> User | None:
        return self._load().get(username.strip().lower())

    def all(self) -> list[User]:
        return sorted(self._load().values(), key=lambda u: u.username)

    def authenticate(self, username: str, password: str) -> User | None:
        user = self.get(username)
        if user is None or user.disabled:
            verify_password(password, _DUMMY_HASH)
            return None
        return user if verify_password(password, user.password_hash) else None

    def create(self, username: str, password: str, role: Role,
               org_id: str | None = None, must_change_password: bool = True) -> User:
        username = username.strip().lower()
        if "@" not in username:
            raise ValueError("Username must be an email address.")
        if problem := check_password_policy(password):
            raise ValueError(problem)
        with self._lock:
            users = self._load()
            if username in users:
                raise ValueError(f"An account for {username} already exists.")
            if (role in HOSPITAL_ROLES) != bool(org_id):
                raise ValueError("Hospital accounts need an organisation; others must not have one.")
            user = User(username, role, hash_password(password), org_id, must_change_password)
            users[username] = user
            self._save(users)
        return user

    def update(self, username: str, **changes) -> User:
        """Change fields; `password=` is hashed and checked against the policy."""
        with self._lock:
            users = self._load()
            user = users.get(username.strip().lower())
            if user is None:
                raise KeyError(username)
            if "password" in changes:
                password = changes.pop("password")
                if problem := check_password_policy(password):
                    raise ValueError(problem)
                user.password_hash = hash_password(password)
            for key, value in changes.items():
                if key not in {"role", "org_id", "must_change_password", "disabled"}:
                    raise ValueError(f"Cannot change {key}")
                setattr(user, key, value)
            self._save(users)
        return user


user_store = UserStore()
