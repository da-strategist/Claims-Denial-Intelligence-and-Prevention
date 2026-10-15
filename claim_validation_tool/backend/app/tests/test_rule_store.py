from app.data.rules import RuleRepository
from app.data.seed_rules import DEFAULT_RULES
from app.models import RuleCreate, RuleUpdate

NEW_RULE = RuleCreate(
    name="Custom rule",
    category="Billing",
    severity="info",
    conditions=[{"field": "total_paid", "operator": "equals", "value": "0"}],
)


def test_seeds_and_writes_file_when_missing(tmp_path):
    path = tmp_path / "rules.json"
    store = RuleRepository(path=path)
    assert path.exists()
    assert len(store.list()) == len(DEFAULT_RULES)


def test_changes_survive_reload(tmp_path):
    path = tmp_path / "rules.json"
    store = RuleRepository(path=path)
    created = store.create(NEW_RULE)
    store.update("RULE-001", RuleUpdate(enabled=False))
    store.delete("RULE-002")

    reloaded = RuleRepository(path=path)
    assert reloaded.get(created.id) == created
    assert reloaded.get("RULE-001").enabled is False
    assert reloaded.get("RULE-002") is None
    assert len(reloaded.list()) == len(DEFAULT_RULES)


def test_deleted_ids_are_not_reused_after_reload(tmp_path):
    path = tmp_path / "rules.json"
    store = RuleRepository(path=path)
    last = store.create(NEW_RULE)
    store.delete(last.id)

    assert RuleRepository(path=path).create(NEW_RULE).id != last.id


def test_without_path_nothing_is_written(tmp_path):
    RuleRepository().create(NEW_RULE)
    assert list(tmp_path.iterdir()) == []
