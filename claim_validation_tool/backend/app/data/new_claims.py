"""Claims entered in the app, saved to a JSON file so they survive restarts.

The source CSVs are never modified. Each record holds what ClaimsRepository.add_claim was
given and, once the claim is submitted, the date it was submitted; on startup the
repository replays them in order. The file holds patient IDs and codes, so it is written
readable only by this account.
"""

import json
import os
from datetime import date
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any

DEFAULT_NEW_CLAIMS_FILE = Path(__file__).resolve().parents[2] / "new_claims.json"


class NewClaimStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._records: list[dict[str, Any]] = []
        self._next_control = 1
        self._lock = Lock()
        if path is not None and path.exists():
            data = json.loads(path.read_text())
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
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            payload = {"next_control_number": self._next_control, "claims": self._records}
            f.write(json.dumps(payload, indent=2))
        tmp.replace(self.path)


@lru_cache(maxsize=1)
def get_new_claim_store() -> NewClaimStore:
    """Process-wide store saved to RCM_NEW_CLAIMS_FILE."""
    return NewClaimStore(Path(os.environ.get("RCM_NEW_CLAIMS_FILE", DEFAULT_NEW_CLAIMS_FILE)))
