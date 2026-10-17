"""Emergency (break-glass) access: a platform account looking inside one organisation.

The platform has no access to organisations' data by default. In an emergency (e.g. a
support case the organisation can't resolve alone) a platform account can grant itself
access to one organisation, giving a reason. Access is read-only (EMERGENCY_PERMISSIONS),
ends at a set time, can be ended early by the platform or by the organisation's
administrators, and everything done with it is in the organisation's own audit log.
Grants are kept (never deleted) in break_glass.json beside organisations.json.
"""

import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from threading import Lock

from pydantic import BaseModel, Field

from app.data.orgs import get_org_registry

MIN_MINUTES, MAX_MINUTES = 15, 240


class EmergencyAccess(BaseModel):
    id: str
    organisation_id: str
    username: str = Field(description="The platform account")
    reason: str
    granted_at: datetime
    expires_at: datetime
    ended_at: datetime | None = None
    ended_by: str | None = None

    def active(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        return self.ended_at is None and now < self.expires_at


class EmergencyAccessStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()
        self._grants: list[EmergencyAccess] = []
        if path.exists():
            self._grants = [EmergencyAccess.model_validate(g) for g in json.loads(path.read_text())["grants"]]

    def grant(self, username: str, organisation_id: str, reason: str, minutes: int) -> EmergencyAccess:
        """Start access, ending any other access the account still has open."""
        now = datetime.now(UTC)
        with self._lock:
            for grant in self._grants:
                if grant.username == username and grant.active(now):
                    grant.ended_at, grant.ended_by = now, username
            grant = EmergencyAccess(
                id=f"EA-{secrets.token_hex(4)}",
                organisation_id=organisation_id,
                username=username,
                reason=reason,
                granted_at=now,
                expires_at=now + timedelta(minutes=minutes),
            )
            self._grants.append(grant)
            self._save()
            return grant

    def active_for(self, username: str) -> EmergencyAccess | None:
        now = datetime.now(UTC)
        return next((g for g in reversed(self._grants) if g.username == username and g.active(now)), None)

    def for_organisation(self, organisation_id: str) -> list[EmergencyAccess]:
        """Newest first."""
        return [g for g in reversed(self._grants) if g.organisation_id == organisation_id]

    def all(self) -> list[EmergencyAccess]:
        return list(reversed(self._grants))

    def end(self, grant_id: str, by: str) -> EmergencyAccess | None:
        with self._lock:
            grant = next((g for g in self._grants if g.id == grant_id), None)
            if grant is not None and grant.active():
                grant.ended_at, grant.ended_by = datetime.now(UTC), by
                self._save()
            return grant

    def _save(self) -> None:
        payload = {"grants": [g.model_dump(mode="json") for g in self._grants]}
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(payload, indent=2))
        tmp.replace(self.path)


@lru_cache(maxsize=1)
def get_emergency_access() -> EmergencyAccessStore:
    root = get_org_registry().root
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return EmergencyAccessStore(root / "break_glass.json")
