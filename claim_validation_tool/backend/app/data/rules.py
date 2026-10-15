"""In-memory rule store, seeded with the default rule set.

Rules live for the life of the process: edits are lost on restart. Swap this for a
database-backed store when rules need to persist.
"""

from datetime import UTC, datetime
from functools import lru_cache
from threading import Lock

from app.data.seed_rules import DEFAULT_RULES
from app.models import Rule, RuleCreate, RuleUpdate


class RuleRepository:
    def __init__(self, seed: list[RuleCreate] = DEFAULT_RULES) -> None:
        self._rules: dict[str, Rule] = {}
        self._next_number = 1
        self._lock = Lock()  # sync routes run in a threadpool
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
            return rule

    def replace(self, rule_id: str, data: RuleCreate) -> Rule | None:
        return self._save(rule_id, data.model_dump())

    def update(self, rule_id: str, changes: RuleUpdate) -> Rule | None:
        return self._save(rule_id, changes.model_dump(exclude_unset=True))

    def delete(self, rule_id: str) -> bool:
        with self._lock:
            return self._rules.pop(rule_id, None) is not None

    def _save(self, rule_id: str, fields: dict) -> Rule | None:
        with self._lock:
            existing = self._rules.get(rule_id)
            if existing is None:
                return None
            # Re-validate the merged rule so cross-field checks still apply
            rule = Rule.model_validate(
                {**existing.model_dump(), **fields, "updated_at": datetime.now(UTC)}
            )
            self._rules[rule_id] = rule
            return rule


@lru_cache(maxsize=1)
def get_rule_repository() -> RuleRepository:
    """Process-wide rule store, usable as a FastAPI dependency."""
    return RuleRepository()
