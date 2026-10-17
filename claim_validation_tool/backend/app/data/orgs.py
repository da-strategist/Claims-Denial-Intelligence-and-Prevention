"""Organisations: each one's data is kept apart from every other's (HIPAA).

Every organisation has its own folder under RCM_ORGS_DIR holding its app data (rules,
corrections, drafts, new claims, registrations, 837 settings, audit log), plus a claims
data folder (its CSVs). Stores and caches are created per organisation from these paths,
and requests reach them only through the signed-in user's organisation, so one
organisation's data is never in another's stores. See DATA_SEGREGATION_PLAN.md.

    backend/orgs/
      organisations.json
      meridian/   rules.json  claim_corrections.json  claim_drafts.json  new_claims.json
                  patient_registrations.json  edi_settings.json  logs/audit.jsonl
"""

import json
import os
from datetime import UTC, datetime
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Annotated

from pydantic import BaseModel, StringConstraints

DEFAULT_ORGS_DIR = Path(__file__).resolve().parents[2] / "orgs"

OrgId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{1,31}$")]


class OrgStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class Organisation(BaseModel):
    id: OrgId
    name: str
    data_dir: str  # its claims CSVs; relative paths are from the orgs folder
    status: OrgStatus = OrgStatus.ACTIVE
    created_at: datetime


class OrgRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._path = root / "organisations.json"
        self._lock = Lock()
        self._orgs: dict[str, Organisation] = {}
        if self._path.exists():
            for item in json.loads(self._path.read_text())["organisations"]:
                org = Organisation.model_validate(item)
                self._orgs[org.id] = org

    def list(self) -> list[Organisation]:
        return sorted(self._orgs.values(), key=lambda org: org.id)

    def get(self, org_id: str) -> Organisation | None:
        return self._orgs.get(org_id)

    def add(self, org_id: str, name: str, data_dir: Path) -> Organisation:
        with self._lock:
            if org_id in self._orgs:
                raise ValueError(f"Organisation {org_id} already exists")
            org = Organisation(
                id=org_id, name=name, data_dir=str(data_dir), created_at=datetime.now(UTC)
            )
            self._orgs[org.id] = org
            self.folder(org.id).mkdir(mode=0o700, parents=True, exist_ok=True)
            self._save()
            return org

    def set_status(self, org_id: str, status: OrgStatus) -> Organisation:
        with self._lock:
            org = self._require(org_id).model_copy(update={"status": status})
            self._orgs[org_id] = org
            self._save()
            return org

    def folder(self, org_id: str) -> Path:
        """The organisation's app-data folder."""
        return self.root / org_id

    def data_dir(self, org_id: str) -> Path:
        """The organisation's claims CSVs."""
        org = self._require(org_id)
        path = Path(org.data_dir)
        return path if path.is_absolute() else self.root / path

    def _require(self, org_id: str) -> Organisation:
        org = self._orgs.get(org_id)
        if org is None:
            raise LookupError(f"No organisation {org_id}")
        return org

    def _save(self) -> None:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = {"organisations": [o.model_dump(mode="json") for o in self._orgs.values()]}
        tmp = self._path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(payload, indent=2))
        tmp.replace(self._path)


@lru_cache(maxsize=1)
def get_org_registry() -> OrgRegistry:
    return OrgRegistry(Path(os.environ.get("RCM_ORGS_DIR", DEFAULT_ORGS_DIR)))


def org_file(org_id: str, name: str) -> Path:
    """Path of one of the organisation's app-data files, e.g. org_file(org, "rules.json")."""
    registry = get_org_registry()
    if registry.get(org_id) is None:
        raise LookupError(f"No organisation {org_id}")
    path = registry.folder(org_id) / name
    # Created on first use, readable only by the account running the API (it holds PHI)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path
