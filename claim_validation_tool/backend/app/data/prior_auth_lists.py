"""Which services each payer requires prior authorization for, as the hospital gave them to us.
A claim can't tell us this itself: an 837 only carries a number when someone got one.

One list per payer. A payer without a list is simply not assessed. Holds no patient details, so
it's a settings file. Saved claims keep what was decided when they were saved, so changing a
list never changes a claim that was already handed off, sent or paid.
"""

import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from threading import Lock

from pydantic import BaseModel

from app.data.orgs import org_file
from app.data.secure_files import read_text, write_text


class PriorAuthList(BaseModel):
    payer_id: str
    cpt_codes: list[str]
    updated_at: datetime
    updated_by: str


class PriorAuthListStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._lists: dict[str, PriorAuthList] = {}
        self._lock = Lock()
        if path is not None and path.exists():
            saved = json.loads(read_text(path, None))["lists"]
            self._lists = {item["payer_id"]: PriorAuthList.model_validate(item) for item in saved}

    def _save(self) -> None:
        """Caller holds the lock."""
        if self.path is not None:
            lists = [item.model_dump(mode="json") for item in self._lists.values()]
            write_text(self.path, json.dumps({"lists": lists}, indent=2), None)

    def all(self) -> list[PriorAuthList]:
        with self._lock:
            return sorted(self._lists.values(), key=lambda item: item.payer_id)

    def has_list(self, payer_id: str) -> bool:
        with self._lock:
            return payer_id in self._lists

    def listed_codes(self, payer_id: str, cpt_codes: list[str]) -> list[str]:
        """Those of these codes on the payer's list, if it has one."""
        with self._lock:
            found = self._lists.get(payer_id)
        return [code for code in cpt_codes if code in found.cpt_codes] if found else []

    def put(self, payer_id: str, cpt_codes: list[str], by: str) -> PriorAuthList:
        saved = PriorAuthList(
            payer_id=payer_id, cpt_codes=sorted(set(cpt_codes)), updated_at=datetime.now(UTC), updated_by=by
        )
        with self._lock:
            self._lists[payer_id] = saved
            self._save()
        return saved

    def remove(self, payer_id: str) -> bool:
        with self._lock:
            if self._lists.pop(payer_id, None) is None:
                return False
            self._save()
            return True


@lru_cache
def get_prior_auth_lists(org_id: str) -> PriorAuthListStore:
    return PriorAuthListStore(org_file(org_id, "prior_auth_lists.json"))
