"""Saved drafts of the New Claim form, in a JSON file readable only by this account.

They hold patient IDs, so expired drafts are removed whenever the store is read or written
rather than left to pile up.
"""

import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from threading import Lock

from app.data.orgs import org_file
from app.models import DRAFT_RETENTION_DAYS, DraftForm, SavedDraft

DEFAULT_DRAFTS_FILE = Path(__file__).resolve().parents[2] / "claim_drafts.json"


class DraftStore:
    def __init__(self, path: Path | None = None, retention_days: int = DRAFT_RETENTION_DAYS) -> None:
        self.path = path
        self.retention = timedelta(days=retention_days)
        self._drafts: dict[str, SavedDraft] = {}
        self._lock = Lock()
        if path is not None and path.exists():
            data = json.loads(path.read_text())
            for item in data["drafts"]:
                draft = SavedDraft.model_validate(item)
                self._drafts[draft.id] = draft

    def list(self) -> list[SavedDraft]:
        """Unexpired drafts, most recently saved first."""
        with self._lock:
            self._purge()
            return sorted(self._drafts.values(), key=lambda d: d.updated_at, reverse=True)

    def get(self, draft_id: str) -> SavedDraft | None:
        with self._lock:
            self._purge()
            return self._drafts.get(draft_id)

    def create(self, form: DraftForm, username: str) -> SavedDraft:
        with self._lock:
            self._purge()
            now = datetime.now(UTC)
            draft_id = f"DRF-{secrets.token_hex(4)}"
            while draft_id in self._drafts:
                draft_id = f"DRF-{secrets.token_hex(4)}"
            draft = SavedDraft(
                id=draft_id,
                form=form,
                created_by=username,
                created_at=now,
                updated_by=username,
                updated_at=now,
                expires_at=now + self.retention,
            )
            self._drafts[draft_id] = draft
            self._save()
            return draft

    def update(self, draft_id: str, form: DraftForm, username: str) -> SavedDraft | None:
        """Replace the form. Saving restarts the expiry clock."""
        with self._lock:
            self._purge()
            if draft_id not in self._drafts:
                return None
            now = datetime.now(UTC)
            draft = self._drafts[draft_id].model_copy(
                update={
                    "form": form,
                    "updated_by": username,
                    "updated_at": now,
                    "expires_at": now + self.retention,
                }
            )
            self._drafts[draft_id] = draft
            self._save()
            return draft

    def delete(self, draft_id: str) -> bool:
        with self._lock:
            removed = self._drafts.pop(draft_id, None)
            self._purge(save=removed is None)
            if removed:
                self._save()
            return removed is not None

    def _purge(self, save: bool = True) -> None:
        """Drop expired drafts. Caller holds the lock."""
        now = datetime.now(UTC)
        expired = [d.id for d in self._drafts.values() if d.expires_at <= now]
        for draft_id in expired:
            del self._drafts[draft_id]
        if expired and save:
            self._save()

    def _save(self) -> None:
        """Write every draft atomically, readable only by this account. Caller holds the lock."""
        if self.path is None:
            return
        payload = {"drafts": [d.model_dump(mode="json") for d in self._drafts.values()]}
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(payload, indent=2))
        tmp.replace(self.path)


@lru_cache(maxsize=None)
def get_draft_store(org_id: str) -> DraftStore:
    """The organisation's saved drafts, in its folder."""
    return DraftStore(org_file(org_id, "claim_drafts.json"))
