"""The validation snapshot validates only the claims that changed since it was built."""

import pandas as pd
import pytest

from app.data.rules import RuleRepository
from app.models import RuleUpdate
from app.services import status_snapshot
from app.services.status_snapshot import StatusSnapshot
from app.services.validation_engine import validate_claims

CLAIM = "CLM0000002"


@pytest.fixture
def rules(tmp_path):
    return RuleRepository(path=tmp_path / "rules.json")


@pytest.fixture
def validated(monkeypatch):
    """The claim IDs each validation run was given."""
    runs: list[list[str]] = []

    def spy(claims, rules):
        runs.append(list(claims["claim_id"]))
        return validate_claims(claims, rules)

    monkeypatch.setattr(status_snapshot, "validate_claims", spy)
    return runs


def full(repo, rules) -> pd.DataFrame:
    """What validating every claim from scratch gives."""
    return StatusSnapshot().get(repo, rules.list())


def test_a_fix_validates_only_that_claim(repo, rules, validated):
    snapshot = StatusSnapshot()
    before = snapshot.get(repo, rules.list())
    assert len(validated) == 1 and len(validated[0]) == len(before)

    repo.apply_overrides({CLAIM: {"is_clean_claim": "true", "pa_number": "Z1"}})
    after = snapshot.get(repo, rules.list())
    assert validated[1] == [CLAIM]
    pd.testing.assert_frame_equal(after, full(repo, rules))
    assert after is not before  # callers holding the old frame keep it unchanged

    # Undoing the fix brings back the original result, again for that claim alone
    repo.apply_overrides({})
    assert snapshot.get(repo, rules.list()).equals(before)
    assert validated[3] == [CLAIM]


def test_nothing_changed_validates_nothing(repo, rules, validated):
    snapshot = StatusSnapshot()
    first = snapshot.get(repo, rules.list())
    assert snapshot.get(repo, rules.list()) is first
    assert len(validated) == 1


def test_a_rule_change_validates_everything(repo, rules, validated):
    snapshot = StatusSnapshot()
    snapshot.get(repo, rules.list())
    rule = rules.list()[0]
    rules.update(rule.id, RuleUpdate(enabled=not rule.enabled))
    snapshot.get(repo, rules.list())
    assert len(validated[1]) == len(validated[0])


def test_too_many_changes_since_validates_everything(repo, rules, validated):
    snapshot = StatusSnapshot()
    snapshot.get(repo, rules.list())
    for _ in range(repo.KEPT_CHANGES + 1):
        repo.apply_overrides({})
    pd.testing.assert_frame_equal(snapshot.get(repo, rules.list()), full(repo, rules))
    assert len(validated[1]) == len(validated[0])
