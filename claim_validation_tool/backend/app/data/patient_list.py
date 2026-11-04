"""What claims have taught us about the organisation's patients. The hospital's own register
stays the master: this is a working copy, kept to the few details claims need.

The patient table a hospital starts with is never modified. Patients first seen on a claim,
and newer details for known patients, are saved here and laid over it at startup
(ClaimsRepository). Holds names, so it's PHI: encrypted, and owner-only.
"""

import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any

from cryptography.fernet import Fernet

from app.data.orgs import org_cipher_for, org_file
from app.data.secure_files import read_text, write_text


class PatientListStore:
    def __init__(self, path: Path | None = None, cipher: Fernet | None = None) -> None:
        self.path = path
        self._cipher = cipher
        self._records: dict[str, dict[str, Any]] = {}
        self._lock = Lock()
        if path is not None and path.exists():
            self._records = json.loads(read_text(path, cipher))["patients"]

    def _save(self) -> None:
        """Caller holds the lock."""
        if self.path is not None:
            write_text(self.path, json.dumps({"patients": self._records}, indent=2), self._cipher)

    def records(self) -> dict[str, dict[str, Any]]:
        """patient_id -> {row, added, added_at, added_by, review}."""
        with self._lock:
            return {key: dict(record) for key, record in self._records.items()}

    def add(self, patient_id: str, row: dict[str, Any], by: str, review: list[str]) -> None:
        with self._lock:
            self._records[patient_id] = {
                "row": row,
                "added": True,
                "added_at": datetime.now(UTC).isoformat(),
                "added_by": by,
                "review": review,
            }
            self._save()

    def update(self, patient_id: str, changes: dict[str, Any]) -> None:
        with self._lock:
            record = self._records.setdefault(patient_id, {"row": {}, "added": False, "review": []})
            record["row"] = {**record["row"], **changes}
            self._save()

    def restore(self, patient_id: str, record: dict[str, Any] | None) -> None:
        """Put a patient's record back as it was, or remove it (None)."""
        with self._lock:
            if record is None:
                self._records.pop(patient_id, None)
            else:
                self._records[patient_id] = record
            self._save()

    def to_review(self) -> dict[str, list[str]]:
        """Patients who may be someone already on the list -> who they may be."""
        with self._lock:
            return {key: list(r["review"]) for key, r in self._records.items() if r.get("review")}

    def clear_review(self, patient_id: str) -> bool:
        """A person has checked: this is a different patient. False if it wasn't flagged."""
        with self._lock:
            record = self._records.get(patient_id)
            if record is None or not record.get("review"):
                return False
            record["review"] = []
            self._save()
            return True


@lru_cache(maxsize=None)
def get_patient_list(org_id: str) -> PatientListStore:
    return PatientListStore(org_file(org_id, "patient_list.json"), org_cipher_for(org_id))
