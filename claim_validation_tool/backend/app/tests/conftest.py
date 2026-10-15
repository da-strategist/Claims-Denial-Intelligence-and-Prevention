from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.data.repository import ClaimsRepository, get_repository
from app.main import app

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def repo() -> ClaimsRepository:
    return ClaimsRepository(FIXTURES_DIR)


@pytest.fixture
def client(monkeypatch) -> TestClient:
    # Point both the startup preload and the request dependency at the fixtures
    monkeypatch.setenv("RCM_DATA_DIR", str(FIXTURES_DIR))
    get_repository.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    get_repository.cache_clear()
