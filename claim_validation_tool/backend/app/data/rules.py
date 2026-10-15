"""Rule store, seeded with the default rule set and optionally saved to a JSON file.

With a `path`, rules are loaded from the file if it exists (otherwise seeded and
written), and every change is written back, so rules survive restarts. Without
one, rules live in memory only (used by tests).
"""

import json
import os
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from threading import Lock

from app.data.seed_rules import DEFAULT_RULES
from app.models import Rule, RuleCreate, RuleUpdate

DEFAULT_RULES_FILE = Path(__file__).resolve().parents[2] / "rules.json"


class RuleRepository:
    def __init__(self, seed: list[RuleCreate] = DEFAULT_RULES, path: Path | None = None) -> None:
        self.path = path
        self._rules: dict[str, Rule] = {}
        self._next_number = 1
        self._lock = Lock()  # sync routes run in a threadpool

        if path is not None and path.exists():
            self._load(path)
        else:
            for rule in seed:
                self.create(rule)

    def list(self) -> list[Rule]:
        return list(self._rules.values())

    def get(self, rule_id: str) -> Rule | None:
        return self._rules.get(rule_id)

    def create(self, data: RuleCreate) -> Rule:
        with self._lock:
            now = datetime.now(UTC)
            rule = Rule(
                **data.model_dump(),
                id=f"RULE-{self._next_number:03d}",
                created_at=now,
                updated_at=now,
            )
            self._next_number += 1
            self._rules[rule.id] = rule
            self._save()
            return rule

    def replace(self, rule_id: str, data: RuleCreate) -> Rule | None:
        return self._update(rule_id, data.model_dump())

    def update(self, rule_id: str, changes: RuleUpdate) -> Rule | None:
        return self._update(rule_id, changes.model_dump(exclude_unset=True))

    def delete(self, rule_id: str) -> bool:
        with self._lock:
            if self._rules.pop(rule_id, None) is None:
                return False
            self._save()
            return True

    def _update(self, rule_id: str, fields: dict) -> Rule | None:
        with self._lock:
            existing = self._rules.get(rule_id)
            if existing is None:
                return None
            # Re-validate the merged rule so cross-field checks still apply
            rule = Rule.model_validate(
                {**existing.model_dump(), **fields, "updated_at": datetime.now(UTC)}
            )
            self._rules[rule_id] = rule
            self._save()
            return rule

    def _load(self, path: Path) -> None:
        data = json.loads(path.read_text())
        rules = [Rule.model_validate(item) for item in data["rules"]]
        self._rules = {rule.id: rule for rule in rules}
        # Never reuse the ID of a deleted rule
        self._next_number = data["next_number"]

    def _save(self) -> None:
        """Write all rules to `path` atomically. Caller holds the lock."""
        if self.path is None:
            return
        payload = {
            "next_number": self._next_number,
            "rules": [rule.model_dump(mode="json") for rule in self._rules.values()],
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2))
        tmp.replace(self.path)


@lru_cache(maxsize=1)
def get_rule_repository() -> RuleRepository:
    """Process-wide rule store saved to RCM_RULES_FILE, usable as a FastAPI dependency."""
    return RuleRepository(path=Path(os.environ.get("RCM_RULES_FILE", DEFAULT_RULES_FILE)))
