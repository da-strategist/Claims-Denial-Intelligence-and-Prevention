from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.data.corrections import get_correction_store
from app.data.reference import get_reference_data
from app.data import repository
from app.data.repository import ClaimsRepository, get_repository
from app.data.rules import get_rule_repository
from app.main import app
from app.services.status_snapshot import get_status_snapshot

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def repo() -> ClaimsRepository:
    return ClaimsRepository(FIXTURES_DIR)


@pytest.fixture
def client(monkeypatch, tmp_path) -> TestClient:
    # Point both the startup preload and the request dependency at the fixtures,
    # and give each test fresh rule and correction stores saved to temp files
    monkeypatch.setenv("RCM_DATA_DIR", str(FIXTURES_DIR))
    monkeypatch.setenv("RCM_RULES_FILE", str(tmp_path / "rules.json"))
    monkeypatch.setenv("RCM_CORRECTIONS_FILE", str(tmp_path / "corrections.json"))
    caches = (
        get_repository,
        get_rule_repository,
        get_correction_store,
        get_reference_data,
        get_status_snapshot,
    )
    for cache in caches:
        cache.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    for cache in caches:
        cache.cache_clear()


@pytest.fixture
def today(monkeypatch):
    """Pin the repository's clock to 2026-01-10; returns a setter for moving it."""
    current = {"date": date(2026, 1, 10)}
    monkeypatch.setattr(repository, "_today", lambda: current["date"])
    return lambda new_date: current.update(date=new_date)
