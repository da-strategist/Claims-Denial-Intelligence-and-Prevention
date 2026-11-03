"""What was changed on claims by editing them, saved to a JSON file.

AI Fix corrections stay in the CorrectionStore while they can still be undone. Editing a
claim folds its corrections into the claim, so they move here with the edit: together the
two stores say how a claim came to differ from what was first entered or uploaded. Values
can be PHI (a member ID, an address), so the file is encrypted like the claims themselves.
"""

import json
from functools import lru_cache
from pathlib import Path
from threading import Lock

from cryptography.fernet import Fernet

from app.data.orgs import org_cipher_for, org_file
from app.data.secure_files import read_text, write_text
from app.models import ClaimChange


class ClaimChangeLog:
    def __init__(self, path: Path | None = None, cipher: Fernet | None = None) -> None:
        self.path = path
        self._cipher = cipher
        self._changes: dict[str, list[ClaimChange]] = {}
        self._lock = Lock()
        if path is not None and path.exists():
            data = json.loads(read_text(path, cipher))
            self._changes = {
                claim_id: [ClaimChange.model_validate(c) for c in changes]
                for claim_id, changes in data["changes"].items()
            }

    def for_claim(self, claim_id: str) -> list[ClaimChange]:
        with self._lock:
            return list(self._changes.get(claim_id, []))

    def add(self, claim_id: str, changes: list[ClaimChange]) -> None:
        if not changes:
            return
        with self._lock:
            self._changes.setdefault(claim_id, []).extend(changes)
            self._save()

    def _save(self) -> None:
        if self.path is None:
            return
        payload = {
            "changes": {
                claim_id: [c.model_dump(mode="json") for c in changes]
                for claim_id, changes in self._changes.items()
            }
        }
        write_text(self.path, json.dumps(payload, indent=2), self._cipher)


@lru_cache(maxsize=None)
def get_claim_change_log(org_id: str) -> ClaimChangeLog:
    """The organisation's record of edits to claims, saved in its folder."""
    return ClaimChangeLog(org_file(org_id, "claim_changes.json"), org_cipher_for(org_id))
