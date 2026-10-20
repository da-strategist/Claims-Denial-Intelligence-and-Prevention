"""Hospital organisations, patient records, and policy shares (JSON files).

Patient records hold identifying details (name, hospital reference, date of
birth), so these files are gitignored and written owner-only, like
users.json. Encryption at rest is on the go-live list in CLAUDE.md.
"""

import json
import os
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Generic, TypeVar

BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Org:
    org_id: str
    name: str
    disabled: bool = False
    created_at: str = field(default_factory=_now)


@dataclass
class Patient:
    patient_id: str
    org_id: str
    name: str
    reference: str = ""       # the hospital's own patient number (MRN)
    date_of_birth: str = ""   # ISO date, optional
    created_by: str = ""
    created_at: str = field(default_factory=_now)


@dataclass
class Share:
    """An individual lets one hospital see one of their documents."""
    share_id: str
    document_id: str
    org_id: str
    shared_by: str            # the individual's username
    patient_id: str | None = None  # set by the hospital to file it under a patient
    created_at: str = field(default_factory=_now)


@dataclass
class Provider:
    """A healthcare provider an individual keeps for reference (not
    necessarily on the platform)."""
    provider_id: str
    owner: str                # the individual's username
    name: str
    kind: str = "doctor"      # doctor, hospital, clinic, pharmacy, other
    phone: str = ""
    notes: str = ""
    created_at: str = field(default_factory=_now)


T = TypeVar("T")


class JsonStore(Generic[T]):
    def __init__(self, path: Path, cls: type[T], key: str):
        self.path, self.cls, self.key = path, cls, key
        self._lock = Lock()

    def _load(self) -> dict[str, T]:
        if not self.path.exists():
            return {}
        known = {f.name for f in fields(self.cls)}
        return {r[self.key]: self.cls(**{k: v for k, v in r.items() if k in known})
                for r in json.loads(self.path.read_text())}

    def _save(self, items: dict[str, T]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps([asdict(i) for i in items.values()], indent=2))
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)

    def all(self) -> list[T]:
        return list(self._load().values())

    def get(self, item_id: str) -> T | None:
        return self._load().get(item_id)

    def add(self, item: T) -> T:
        with self._lock:
            items = self._load()
            items[getattr(item, self.key)] = item
            self._save(items)
        return item

    def update(self, item_id: str, **changes) -> T:
        with self._lock:
            items = self._load()
            item = items[item_id]
            for k, v in changes.items():
                setattr(item, k, v)
            self._save(items)
        return item

    def remove(self, item_id: str) -> None:
        with self._lock:
            items = self._load()
            items.pop(item_id, None)
            self._save(items)


orgs = JsonStore(Path(os.getenv("ORGS_FILE", str(DATA_DIR / "orgs.json"))), Org, "org_id")
patients = JsonStore(Path(os.getenv("PATIENTS_FILE", str(DATA_DIR / "patients.json"))), Patient, "patient_id")
shares = JsonStore(Path(os.getenv("SHARES_FILE", str(DATA_DIR / "shares.json"))), Share, "share_id")
providers = JsonStore(Path(os.getenv("PROVIDERS_FILE", str(DATA_DIR / "providers.json"))),
                      Provider, "provider_id")
