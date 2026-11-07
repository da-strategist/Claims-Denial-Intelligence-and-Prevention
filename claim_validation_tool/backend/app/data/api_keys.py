"""API keys: how a hospital's own systems reach the claims API (/api/v1) without a person
signing in. Each key belongs to one organisation and can be revoked on its own.

A key is shown once, when it's created. The file keeps only its SHA-256 (a key is long and
random, so a slow hash adds nothing) and is readable only by its owner. Revoked keys stay
listed, so the audit log's `api.<id>` entries can always be traced to a name.
"""

import hashlib
import hmac
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from threading import Lock

from pydantic import BaseModel

from app.data.users import DEFAULT_USERS_FILE

PREFIX = "crcm"
MAX_ACTIVE_KEYS = 10
# When a key was last used is saved at most this often
SAVE_USED_EVERY = timedelta(minutes=5)


class ApiKey(BaseModel):
    id: str
    organisation_id: str
    name: str
    digest: str
    created_at: datetime
    created_by: str
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_by: str | None = None


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def key_id(token: str) -> str | None:
    """The ID inside a key, or None if this can't be one. The ID isn't secret."""
    parts = token.split("_")
    return parts[1] if len(parts) == 3 and parts[0] == PREFIX else None


class ApiKeyStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._keys: dict[str, ApiKey] = {}
        self._lock = Lock()
        if path.exists():
            self._keys = {k["id"]: ApiKey.model_validate(k) for k in json.loads(path.read_text())["keys"]}

    def _save(self) -> None:
        """Owner-only and atomic. Caller holds the lock."""
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps({"keys": [k.model_dump(mode="json") for k in self._keys.values()]}))
        temp.chmod(0o600)
        temp.replace(self.path)

    def create(self, organisation_id: str, name: str, created_by: str) -> tuple[ApiKey, str]:
        """A new key and its token, the only time the token is available. Raises ValueError
        at the limit or if the organisation already has an active key with this name."""
        with self._lock:
            active = [k for k in self.list(organisation_id) if k.revoked_at is None]
            if len(active) >= MAX_ACTIVE_KEYS:
                raise ValueError(f"An organisation can have up to {MAX_ACTIVE_KEYS} active keys; revoke one first")
            if any(k.name.lower() == name.lower() for k in active):
                raise ValueError(f"There's already an active key named {name}")
            new_id = secrets.token_hex(4)
            token = f"{PREFIX}_{new_id}_{secrets.token_urlsafe(32).replace('_', '-')}"
            key = ApiKey(
                id=new_id,
                organisation_id=organisation_id,
                name=name,
                digest=_digest(token),
                created_at=datetime.now(UTC),
                created_by=created_by,
            )
            self._keys[new_id] = key
            self._save()
        return key, token

    def get(self, id_: str) -> ApiKey | None:
        return self._keys.get(id_)

    def list(self, organisation_id: str) -> list[ApiKey]:
        return sorted(
            (k for k in self._keys.values() if k.organisation_id == organisation_id),
            key=lambda k: k.created_at,
        )

    def verify(self, token: str) -> ApiKey | None:
        """The active key for this token, marked as used now, or None."""
        id_ = key_id(token)
        key = self._keys.get(id_) if id_ else None
        if key is None or key.revoked_at is not None or not hmac.compare_digest(key.digest, _digest(token)):
            return None
        now = datetime.now(UTC)
        with self._lock:
            stale = key.last_used_at is None or now - key.last_used_at >= SAVE_USED_EVERY
            if stale:
                key.last_used_at = now
                self._save()
        return key

    def revoke(self, organisation_id: str, id_: str, by: str) -> ApiKey | None:
        """Stop a key working. None if this organisation has no such key; already revoked
        stays as it was."""
        with self._lock:
            key = self._keys.get(id_)
            if key is None or key.organisation_id != organisation_id:
                return None
            if key.revoked_at is None:
                key.revoked_at, key.revoked_by = datetime.now(UTC), by
                self._save()
            return key

    def revoke_organisation(self, organisation_id: str, by: str) -> int:
        """Revoke all of a deleted organisation's keys; returns how many were active."""
        active = [k.id for k in self.list(organisation_id) if k.revoked_at is None]
        for id_ in active:
            self.revoke(organisation_id, id_, by)
        return len(active)


@lru_cache(maxsize=1)
def get_api_keys() -> ApiKeyStore:
    """Process-wide, kept beside the accounts file."""
    users_file = Path(os.environ.get("RCM_USERS_FILE", DEFAULT_USERS_FILE))
    return ApiKeyStore(users_file.with_name("api_keys.json"))
