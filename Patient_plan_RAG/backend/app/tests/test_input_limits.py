"""Input validation, upload hardening, and rate limiting."""

import pytest

from backend.app import rate_limit
from backend.app.models.common import DISCLAIMER, MAX_QUESTION_CHARS
from backend.app.routers import policies
from backend.app.services.retrieval import load_chunks
from backend.app.tests.conftest import POLICY_PDF


# ── Document IDs (used as file names) ────────────────────────────────

@pytest.mark.parametrize("bad_id", ["../policies/_registry", "a/b", "a.b", "x" * 65, ""])
def test_chat_rejects_unsafe_policy_id(client, bad_id):
    resp = client.post("/api/chat", json={"question": "Is MRI covered?", "policy_id": bad_id})
    assert resp.status_code == 422


@pytest.mark.parametrize("path", ["/assess", "/auth-checklist"])
def test_coverage_rejects_unsafe_document_id(client, path):
    resp = client.post(f"/api/coverage{path}",
                       json={"service_name": "MRI", "document_id": "../policies/_registry"})
    assert resp.status_code == 422


@pytest.mark.parametrize("suffix", ["", "/summary", "/chunks"])
def test_policy_routes_reject_unsafe_id(client, suffix):
    assert client.get(f"/api/policies/bad.id{suffix}").status_code == 422


def test_load_chunks_refuses_unsafe_id(data_dirs):
    (data_dirs["policies"] / "secret.json").write_text("[]")
    assert load_chunks(data_dirs["chunks"], "../policies/secret") == []


# ── Field lengths ────────────────────────────────────────────────────

def test_question_length_limits(client):
    assert client.post("/api/chat", json={"question": "   "}).status_code == 422
    too_long = "MRI " * (MAX_QUESTION_CHARS // 4 + 1)
    assert client.post("/api/chat", json={"question": too_long}).status_code == 422
    ok = client.post("/api/chat", json={"question": "  Is MRI covered?  "})
    assert ok.status_code == 200


def test_service_and_code_length_limits(client, doc_id):
    url = "/api/coverage/assess"
    assert client.post(url, json={"service_name": "", "document_id": doc_id}).status_code == 422
    assert client.post(url, json={"service_name": "x" * 201, "document_id": doc_id}).status_code == 422
    assert client.post(url, json={"service_name": "MRI", "service_code": "1" * 21,
                                  "document_id": doc_id}).status_code == 422


def test_chunk_page_size_is_bounded(client, doc_id):
    assert client.get(f"/api/policies/{doc_id}/chunks", params={"page_size": 101}).status_code == 422
    assert client.get(f"/api/policies/{doc_id}/chunks", params={"page": 0}).status_code == 422


# ── Uploads ──────────────────────────────────────────────────────────

def test_upload_rejects_non_pdf_content(client, data_dirs):
    resp = client.post("/api/policies/upload",
                       files={"file": ("fake.pdf", b"MZ\x90\x00 not a pdf", "application/pdf")})
    assert resp.status_code == 400
    assert list(data_dirs["uploads"].iterdir()) == []


def test_upload_rejects_empty_file(client, data_dirs):
    resp = client.post("/api/policies/upload", files={"file": ("empty.pdf", b"", "application/pdf")})
    assert resp.status_code == 400
    assert list(data_dirs["uploads"].iterdir()) == []


def test_upload_rejects_oversized_file(client, data_dirs, monkeypatch):
    monkeypatch.setattr(policies, "MAX_UPLOAD_BYTES", 1024)
    resp = client.post("/api/policies/upload",
                       files={"file": ("big.pdf", b"%PDF-" + b"0" * 2048, "application/pdf")})
    assert resp.status_code == 413
    assert list(data_dirs["uploads"].iterdir()) == []


def test_upload_filename_cannot_escape_upload_dir(client, data_dirs, tmp_path):
    with POLICY_PDF.open("rb") as f:
        resp = client.post("/api/policies/upload",
                           files={"file": ("../../evil name.pdf", f, "application/pdf")})
    assert resp.status_code == 200
    saved = list(data_dirs["uploads"].iterdir())
    assert len(saved) == 1
    assert saved[0].name.endswith("_evil_name.pdf")
    assert not (tmp_path / "evil name.pdf").exists()


@pytest.mark.parametrize("name,expected", [
    ("plan.pdf", "plan.pdf"),
    ("../../etc/passwd.pdf", "passwd.pdf"),
    ("C:\\Users\\x\\plan 2025.pdf", "plan_2025.pdf"),
    ("...pdf", "pdf"),
    ("", "upload.pdf"),
])
def test_safe_filename(name, expected):
    assert policies._safe_filename(name) == expected


# ── Rate limiting ────────────────────────────────────────────────────

def test_api_rate_limit_returns_429_with_headers(client, monkeypatch):
    monkeypatch.setattr(rate_limit.api_limiter, "limit", 3)
    rate_limit.api_limiter.reset()  # don't count the fixture's sign-in
    codes = [client.get("/api/dashboard").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    resp = client.get("/api/dashboard")
    assert int(resp.headers["Retry-After"]) >= 1
    assert resp.headers["X-Disclaimer"] == DISCLAIMER


def test_health_is_exempt_from_rate_limit(client, monkeypatch):
    monkeypatch.setattr(rate_limit.api_limiter, "limit", 1)
    assert all(client.get("/api/health").status_code == 200 for _ in range(5))


def test_upload_has_its_own_stricter_limit(client, monkeypatch):
    monkeypatch.setattr(rate_limit.upload_limiter, "limit", 1)
    upload = lambda: client.post("/api/policies/upload",  # noqa: E731
                                 files={"file": ("x.pdf", b"%PDF-1.4 x", "application/pdf")})
    assert upload().status_code == 200
    assert upload().status_code == 429
    assert client.get("/api/dashboard").status_code == 200


def test_sliding_window_expires_old_hits(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: now[0])
    limiter = rate_limit.SlidingWindowLimiter(limit=2, window_seconds=60)
    assert limiter.check("a") is None and limiter.check("a") is None
    assert limiter.check("a") == pytest.approx(60)
    assert limiter.check("b") is None  # other clients unaffected
    now[0] += 60
    assert limiter.check("a") is None
