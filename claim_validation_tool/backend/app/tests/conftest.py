from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.data.repository import ClaimsRepository, get_repository
from app.data.rules import get_rule_repository
from app.main import app

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def repo() -> ClaimsRepository:
    return ClaimsRepository(FIXTURES_DIR)


@pytest.fixture
def client(monkeypatch) -> TestClient:
    # Point both the startup preload and the request dependency at the fixtures,
    # and give each test a freshly seeded rule store
    monkeypatch.setenv("RCM_DATA_DIR", str(FIXTURES_DIR))
    get_repository.cache_clear()
    get_rule_repository.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    get_repository.cache_clear()
    get_rule_repository.cache_clear()
