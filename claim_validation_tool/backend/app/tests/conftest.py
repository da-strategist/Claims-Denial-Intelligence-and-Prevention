import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.data.audit import get_audit_log
from app.data.corrections import get_correction_store
from app.data.drafts import get_draft_store
from app.data.new_claims import get_new_claim_store
from app.data.registrations import get_registration_store
from app.data.knowledge import get_knowledge_base
from app.data.reference import get_reference_data
from app.data import repository
from app.data.repository import ClaimsRepository, get_repository
from app.data.rules import get_rule_repository
from app.data.users import get_user_store, hash_password
from app.main import app
from app.models import Role
from app.services.assistant import get_answer_writer, get_name_scrubber, get_retriever
from app.services.auth import (
    SESSION_COOKIE,
    get_login_throttle,
    get_session_store,
)
from app.services.status_snapshot import get_status_snapshot

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# One account per role, all with this password (hashed once: scrypt is deliberately slow)
TEST_PASSWORD = "Fixture-password-1"
_TEST_HASH = hash_password(TEST_PASSWORD)
USERNAMES = {role: f"{role}1" for role in Role}


def _write_users(path: Path) -> None:
    now = datetime.now(UTC).isoformat()
    users = [
        {
            "username": username,
            "display_name": f"Test {role}",
            "role": role,
            "password_hash": _TEST_HASH,
            "active": True,
            "created_at": now,
            "password_changed_at": now,
        }
        for role, username in USERNAMES.items()
    ]
    path.write_text(json.dumps({"users": users}))


def sign_in(client: TestClient, role: Role) -> TestClient:
    """Give the client a session as the test user with `role` (skips the slow password check)."""
    token = get_session_store().create(USERNAMES[role])
    client.cookies.set(SESSION_COOKIE, token)
    return client


@pytest.fixture
def repo() -> ClaimsRepository:
    return ClaimsRepository(FIXTURES_DIR)


@pytest.fixture
def anon_client(monkeypatch, tmp_path) -> TestClient:
    """A client that isn't signed in. See `client` for one signed in as an admin."""
    # Point both the startup preload and the request dependency at the fixtures,
    # and give each test fresh rule, correction, draft, new-claim, account, and audit stores in temp files
    monkeypatch.setenv("RCM_DATA_DIR", str(FIXTURES_DIR))
    monkeypatch.setenv("RCM_RULES_FILE", str(tmp_path / "rules.json"))
    monkeypatch.setenv("RCM_CORRECTIONS_FILE", str(tmp_path / "corrections.json"))
    monkeypatch.setenv("RCM_DRAFTS_FILE", str(tmp_path / "drafts.json"))
    monkeypatch.setenv("RCM_NEW_CLAIMS_FILE", str(tmp_path / "new_claims.json"))
    monkeypatch.setenv("RCM_REGISTRATIONS_FILE", str(tmp_path / "registrations.json"))
    monkeypatch.setenv("RCM_EDI_SETTINGS_FILE", str(tmp_path / "edi_settings.json"))
    users_file = tmp_path / "users.json"
    _write_users(users_file)
    monkeypatch.setenv("RCM_USERS_FILE", str(users_file))
    monkeypatch.setenv("RCM_AUDIT_FILE", str(tmp_path / "audit.jsonl"))
    # The assistant never calls Claude in tests; tests that need an LLM inject a fake one
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    caches = (
        get_repository,
        get_rule_repository,
        get_correction_store,
        get_draft_store,
        get_new_claim_store,
        get_registration_store,
        get_reference_data,
        get_status_snapshot,
        get_knowledge_base,
        get_retriever,
        get_answer_writer,
        get_name_scrubber,
        get_user_store,
        get_session_store,
        get_login_throttle,
        get_audit_log,
    )
    for cache in caches:
        cache.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    for cache in caches:
        cache.cache_clear()


@pytest.fixture
def client(anon_client) -> TestClient:
    """Signed in as an admin, who may do everything."""
    return sign_in(anon_client, Role.ADMIN)


@pytest.fixture
def today(monkeypatch):
    """Pin the repository's clock to 2026-01-10; returns a setter for moving it."""
    current = {"date": date(2026, 1, 10)}
    monkeypatch.setattr(repository, "_today", lambda: current["date"])
    return lambda new_date: current.update(date=new_date)
