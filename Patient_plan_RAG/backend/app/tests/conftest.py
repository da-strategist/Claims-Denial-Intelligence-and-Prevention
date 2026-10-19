"""Shared fixtures: the synthetic policy, its chunks, and an isolated app.

Each router reads its data directories at import time, so `data_dirs`
repoints every module's directory constants at a temp dir, copies the
synthetic policy in, and lets the app's startup lifespan ingest it.
"""

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import main, rate_limit
from backend.app.routers import chat, coverage, dashboard, policies
from backend.app.services import retrieval
from backend.app.services.conversations import store as conversation_store
from backend.app.services.document_processor import chunk_text, extract_text_from_pdf

POLICY_PDF = (
    Path(__file__).resolve().parents[3] / "data" / "policies" / "apex_health_gold_ppo_2025.pdf"
)


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
    for d in dirs.values():
        d.mkdir()
    shutil.copy(POLICY_PDF, dirs["policies"])

    for module in (main, policies, dashboard):
        monkeypatch.setattr(module, "POLICY_DIR", dirs["policies"])
    for module in (main, policies, chat, coverage, dashboard):
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


@pytest.fixture
def client(data_dirs):
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def doc_id(client):
    return client.get("/api/policies").json()[0]["document_id"]
