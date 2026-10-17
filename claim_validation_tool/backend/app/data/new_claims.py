"""Claims entered in the app, saved to a JSON file so they survive restarts.

The source CSVs are never modified. Each record holds what ClaimsRepository.add_claim was
given and, once the claim is submitted, the date it was submitted; on startup the
repository replays them in order. The file holds patient IDs and codes, so it is written
readable only by this account.
"""

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any

from cryptography.fernet import Fernet

from app.data.orgs import org_cipher_for, org_file
from app.data.secure_files import read_text, write_text

DEFAULT_NEW_CLAIMS_FILE = Path(__file__).resolve().parents[2] / "new_claims.json"


class NewClaimStore:
    def __init__(self, path: Path | None = None, cipher: Fernet | None = None) -> None:
        self.path = path
        self._cipher = cipher
        self._records: list[dict[str, Any]] = []
        self._next_control = 1
        self._lock = Lock()
        if path is not None and path.exists():
            data = json.loads(read_text(path, cipher))
            self._records = data["claims"]
            self._next_control = data.get("next_control_number", 1)

    def records(self) -> list[dict[str, Any]]:
        """Saved claims in the order they were entered: {fields, lines, submitted_on, edi}."""
        with self._lock:
            return [dict(record) for record in self._records]

    def add(self, fields: dict[str, Any], lines: list[dict[str, Any]]) -> None:
        with self._lock:
            self._records.append({"fields": fields, "lines": lines, "submitted_on": None, "edi": None})
            self._save()

    def has(self, claim_id: str) -> bool:
        with self._lock:
            return any(r["fields"]["claim_id"] == claim_id for r in self._records)

    def replace(self, fields: dict[str, Any], lines: list[dict[str, Any]]) -> None:
        """Save an unsubmitted claim's edited details in place (it keeps its position)."""
        with self._lock:
            for record in self._records:
                if record["fields"]["claim_id"] == fields["claim_id"]:
                    if record["submitted_on"]:
                        raise ValueError(f"{fields['claim_id']} was submitted; it can't change")
                    record["fields"], record["lines"] = fields, lines
                    self._save()
                    return
        raise LookupError(f"Claim {fields['claim_id']} isn't a saved new claim")

    def next_control_number(self) -> int:
        """A new interchange control number for an 837 (unique, increasing)."""
        with self._lock:
            number = self._next_control
            self._next_control += 1
            self._save()
            return number

    def mark_submitted(self, claim_id: str, on: date, edi: dict[str, Any] | None = None) -> None:
        """Record the submission date and the 837 sent ({text, summary}), if any."""
        with self._lock:
            for record in self._records:
                if record["fields"]["claim_id"] == claim_id:
                    record["submitted_on"] = on.isoformat()
                    record["edi"] = edi
                    self._save()
                    return
        raise LookupError(f"Claim {claim_id} isn't a saved new claim")

    def edi_text(self, claim_id: str) -> str | None:
        with self._lock:
            for record in self._records:
                if record["fields"]["claim_id"] == claim_id and record.get("edi"):
                    return record["edi"]["text"]
        return None

    def _save(self) -> None:
        """Write every record atomically, readable only by this account. Caller holds the lock."""
        if self.path is None:
            return
        payload = {"next_control_number": self._next_control, "claims": self._records}
        write_text(self.path, json.dumps(payload, indent=2), self._cipher)


@lru_cache(maxsize=None)
def get_new_claim_store(org_id: str) -> NewClaimStore:
    """Claims the organisation entered in the app, saved in its folder."""
    return NewClaimStore(org_file(org_id, "new_claims.json"), org_cipher_for(org_id))
