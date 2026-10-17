"""Corrections applied to claims by AI Fix, saved to a JSON file.

Source claim data is never modified: corrections are layered over it by the
ClaimsRepository, and undoing a claim's corrections restores its original values.
"""

import json
import os
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from threading import Lock

from app.models import Correction

DEFAULT_CORRECTIONS_FILE = Path(__file__).resolve().parents[2] / "claim_corrections.json"


class CorrectionStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._corrections: list[Correction] = []
        self._next_number = 1
        self._lock = Lock()
        if path is not None and path.exists():
            data = json.loads(path.read_text())
            self._corrections = [Correction.model_validate(c) for c in data["corrections"]]
            self._next_number = data["next_number"]

    def for_claim(self, claim_id: str) -> list[Correction]:
        return [c for c in self._corrections if c.claim_id == claim_id]

    def overrides(self) -> dict[str, dict[str, str]]:
        """Current corrected value of each field, by claim (later corrections win)."""
        result: dict[str, dict[str, str]] = {}
        for correction in self._corrections:
            result.setdefault(correction.claim_id, {})[correction.field] = correction.new_value
        return result

    def add(
        self,
        claim_id: str,
        suggestion_id: str,
        changes: dict[str, tuple[str | None, str]],
        applied_by: str | None = None,
    ) -> list[Correction]:
        """Record field changes ({field: (old_value, new_value)}) from one applied suggestion,
        and who applied it."""
        with self._lock:
            now = datetime.now(UTC)
            added = []
            for field, (old_value, new_value) in changes.items():
                added.append(
                    Correction(
                        id=f"COR-{self._next_number:05d}",
                        claim_id=claim_id,
                        field=field,
                        old_value=old_value,
                        new_value=new_value,
                        suggestion_id=suggestion_id,
                        applied_at=now,
                        applied_by=applied_by,
                    )
                )
                self._next_number += 1
            self._corrections.extend(added)
            self._save()
            return added

    def clear_claim(self, claim_id: str) -> list[Correction]:
        """Undo every correction on a claim. Returns what was removed."""
        with self._lock:
            removed = [c for c in self._corrections if c.claim_id == claim_id]
            self._corrections = [c for c in self._corrections if c.claim_id != claim_id]
            if removed:
                self._save()
            return removed

    def _save(self) -> None:
        if self.path is None:
            return
        payload = {
            "next_number": self._next_number,
            "corrections": [c.model_dump(mode="json") for c in self._corrections],
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2))
        tmp.replace(self.path)


@lru_cache(maxsize=1)
def get_correction_store() -> CorrectionStore:
    """Process-wide correction store saved to RCM_CORRECTIONS_FILE."""
    return CorrectionStore(Path(os.environ.get("RCM_CORRECTIONS_FILE", DEFAULT_CORRECTIONS_FILE)))
