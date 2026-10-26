"""Shared fixtures: the synthetic policy, its chunks, and an isolated app.

Each router reads its data directories at import time, so `data_dirs`
repoints every module's directory constants at a temp dir, copies the
synthetic policy in, and lets the app's startup lifespan ingest it.
"""

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import audit, main, rate_limit
from backend.app.auth import sessions as auth_sessions
from backend.app.auth.users import Role, user_store
from backend.app.routers import chat, coverage, policies
from backend.app.services import records, registry, retrieval
from backend.app.services.conversations import store as conversation_store
from backend.app.services.document_processor import chunk_text, extract_text_from_pdf

POLICY_PDF = (
    Path(__file__).resolve().parents[3] / "data" / "policies" / "apex_health_gold_ppo_2025.pdf"
)


@pytest.fixture(autouse=True)
def isolated_audit_log(tmp_path, monkeypatch):
    """Every test writes audit entries to its own temp file, never data/."""
    monkeypatch.setattr(audit, "AUDIT_FILE", tmp_path / "audit.log")
    return tmp_path / "audit.log"


@pytest.fixture(scope="session")
def policy_pages() -> list[dict]:
    if not POLICY_PDF.exists():
        pytest.skip("synthetic policy PDF missing; run python -m synthetic_data.generate_policy")
    return extract_text_from_pdf(POLICY_PDF)


@pytest.fixture(scope="session")
def policy_chunks(policy_pages):
    return chunk_text(policy_pages, "testdoc")


@pytest.fixture
def data_dirs(tmp_path, monkeypatch):
    if not POLICY_PDF.exists():
        pytest.skip("synthetic policy PDF missing")
    dirs = {name: tmp_path / name for name in ("policies", "chunks", "uploads")}
    monkeypatch.setattr(user_store, "path", tmp_path / "users.json")
    for store, name in ((records.orgs, "orgs"), (records.patients, "patients"),
                        (records.shares, "shares"), (records.providers, "providers"),
                        (records.checklists, "checklists")):
        monkeypatch.setattr(store, "path", tmp_path / f"{name}.json")
    auth_sessions.sessions.reset()
    auth_sessions.login_throttle.reset()
    for d in dirs.values():
        d.mkdir()
    shutil.copy(POLICY_PDF, dirs["policies"])

    for module in (main, registry):
        monkeypatch.setattr(module, "POLICY_DIR", dirs["policies"])
    for module in (main, policies, chat, coverage):
        monkeypatch.setattr(module, "CHUNK_DIR", dirs["chunks"])
    for module in (main, policies):
        monkeypatch.setattr(module, "UPLOAD_DIR", dirs["uploads"])
    monkeypatch.setattr(retrieval, "POLICY_DIR", dirs["policies"])

    rate_limit.api_limiter.reset()
    rate_limit.upload_limiter.reset()
    conversation_store.reset()

    # Never call the live LLM from tests
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return dirs


TEST_PASSWORD = "test password 123"


def sign_in(client: TestClient, username: str, role: Role = Role.INDIVIDUAL,
            org_id: str | None = None) -> TestClient:
    """Create an account (password already changed) and sign `client` in."""
    if user_store.get(username) is None:
        user_store.create(username, TEST_PASSWORD, role, org_id, must_change_password=False)
    resp = client.post("/api/auth/login", json={"username": username, "password": TEST_PASSWORD})
    assert resp.status_code == 200, resp.text
    return client


@pytest.fixture
def anon_client(data_dirs):
    """Not signed in."""
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def client(data_dirs):
    """Signed in as the platform admin (sees sample documents, e.g. the
    preloaded synthetic policy, and its own uploads, which are samples)."""
    with TestClient(main.app) as c:
        yield sign_in(c, "admin@example.com", Role.PLATFORM_ADMIN)


@pytest.fixture
def doc_id(client):
    return client.get("/api/policies").json()[0]["document_id"]
