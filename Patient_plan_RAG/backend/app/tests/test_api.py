"""Endpoint tests against an isolated data directory.

The `data_dirs`/`client`/`doc_id` fixtures live in conftest.py.
"""

import json
import shutil

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.models.common import DISCLAIMER
from backend.app.tests.conftest import POLICY_PDF


# ── Health / startup ─────────────────────────────────────────────────

def test_health_reports_demo_mode_and_disclaimer(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["mode"] == "demo"
    assert "does not constitute coverage determinations" in body["disclaimer"]


def test_startup_ingests_preloaded_policy(client, data_dirs):
    registry = json.loads((data_dirs["policies"] / "_registry.json").read_text())
    assert len(registry) == 1
    entry = registry[0]
    assert entry["filename"] == POLICY_PDF.name
    assert entry["status"] == "completed"
    assert entry["chunk_count"] > 0
    assert [p.name for p in data_dirs["chunks"].iterdir()] == [f"{entry['document_id']}.json"]


def test_startup_rebuild_reuses_document_id(data_dirs):
    ids = []
    for _ in range(2):
        (data_dirs["policies"] / "_registry.json").unlink(missing_ok=True)
        with TestClient(main.app) as c:
            ids.append(c.get("/api/policies").json()[0]["document_id"])
    assert ids[0] == ids[1]
    assert len(list(data_dirs["chunks"].iterdir())) == 1


# ── Dashboard ────────────────────────────────────────────────────────

def test_dashboard_totals_match_registry(client):
    body = client.get("/api/dashboard").json()
    assert body["total_policies"] == 1
    assert body["total_pages"] == 6
    assert body["total_chunks"] == body["policies"][0]["chunk_count"] > 0
    assert body["mode"] == "demo"
    assert body["policies"][0]["insurer_name"] == "Apex Health Insurance"
    assert body["policies"][0]["plan_name"] == "Gold PPO Plan"


def test_policy_metadata_is_extracted(client, doc_id):
    body = client.get(f"/api/policies/{doc_id}").json()
    assert body["plan_id"] == "AHI-GOLD-2025-PPO"
    assert body["effective_date"] == "2025-01-01"
    assert body["expiration_date"] == "2025-12-31"


# ── Policies ─────────────────────────────────────────────────────────

def test_get_policy(client, doc_id):
    body = client.get(f"/api/policies/{doc_id}").json()
    assert body["document_id"] == doc_id
    assert body["is_synthetic"] is True


def test_get_unknown_policy_404(client):
    assert client.get("/api/policies/nope").status_code == 404
    assert client.get("/api/policies/nope/summary").status_code == 404


def test_chunks_are_paginated(client, doc_id):
    total = client.get(f"/api/policies/{doc_id}").json()["chunk_count"]
    first = client.get(f"/api/policies/{doc_id}/chunks", params={"page": 1, "page_size": 5}).json()
    last = client.get(f"/api/policies/{doc_id}/chunks",
                      params={"page": (total + 4) // 5, "page_size": 5}).json()
    assert first["total"] == total
    assert len(first["items"]) == 5
    assert 1 <= len(last["items"]) <= 5
    assert first["items"][0]["document_id"] == doc_id


def test_summary_finds_exclusions_and_deductible(client, doc_id):
    body = client.get(f"/api/policies/{doc_id}/summary").json()
    assert body["document_id"] == doc_id
    assert body["excluded_services"][0]["service"] == "Cosmetic surgery or procedures"
    assert "Individual In-Network: $1,500" in body["deductible"]["description"]


def test_summary_fields_come_from_their_own_sections(client, doc_id):
    body = client.get(f"/api/policies/{doc_id}/summary").json()
    assert {"service": "Specialist Office Visit",
            "amount": "$50 copay (no deductible)"} in body["copayments"]
    assert "Plan pays 80%" in body["coinsurance"]["description"]
    assert "IN-NETWORK PROVIDERS" in body["network_provisions"]["description"]
    assert "does not require referrals" in body["referral_requirements"]


def test_upload_pdf_is_processed_and_registered(client, data_dirs):
    with POLICY_PDF.open("rb") as f:
        resp = client.post("/api/policies/upload",
                           files={"file": ("my_policy.pdf", f, "application/pdf")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["page_count"] == 6
    assert (data_dirs["chunks"] / f"{body['document_id']}.json").exists()
    assert len(list(data_dirs["uploads"].iterdir())) == 1
    assert body["document_id"] in {p["document_id"] for p in client.get("/api/policies").json()}


def test_upload_rejects_non_pdf_filename(client, data_dirs):
    resp = client.post("/api/policies/upload", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert resp.status_code == 400
    assert list(data_dirs["uploads"].iterdir()) == []


def test_upload_unreadable_pdf_is_registered_as_failed(client):
    resp = client.post("/api/policies/upload",
                       files={"file": ("broken.pdf", b"%PDF-1.4 truncated garbage", "application/pdf")})
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"


# ── Chat ─────────────────────────────────────────────────────────────

def test_chat_answers_with_citations_from_registered_doc(client, doc_id):
    body = client.post("/api/chat", json={
        "question": "Does my plan cover an MRI and is prior authorization required?",
    }).json()
    assert body["confidence"] == "supported"
    assert body["citations"]
    assert {c["document_id"] for c in body["citations"]} == {doc_id}
    assert all(c["page_number"] for c in body["citations"])
    assert "MRI" in body["answer"]
    assert "⚠️" in body["answer"]
    assert body["follow_up_suggestions"]


def test_chat_ignores_orphaned_chunk_files(client, data_dirs, doc_id):
    shutil.copy(data_dirs["chunks"] / f"{doc_id}.json", data_dirs["chunks"] / "orphan000000.json")
    body = client.post("/api/chat", json={"question": "Is acupuncture covered?"}).json()
    assert {c["document_id"] for c in body["citations"]} == {doc_id}


def test_chat_off_topic_returns_insufficient_evidence(client):
    body = client.post("/api/chat", json={"question": "Is laser tattoo removal covered?"}).json()
    assert body["confidence"] == "insufficient_evidence"
    assert body["citations"] == []
    assert "could not find sufficient evidence" in body["answer"]


def test_chat_scoped_to_unknown_policy_finds_nothing(client):
    body = client.post("/api/chat", json={"question": "Is acupuncture covered?",
                                          "policy_id": "nope"}).json()
    assert body["confidence"] == "insufficient_evidence"


def test_chat_requires_question(client):
    assert client.post("/api/chat", json={}).status_code == 422


# ── Coverage ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("service,classification,prior_auth", [
    ("MRI", "conditional_coverage", True),
    ("Acupuncture", "exclusion_identified", False),
])
def test_assess_classifies_service(client, doc_id, service, classification, prior_auth):
    body = client.post("/api/coverage/assess",
                       json={"service_name": service, "document_id": doc_id}).json()
    assert body["classification"] == classification
    assert body["prior_auth_required"] is prior_auth
    assert body["citations"]
    assert "General" not in body["explanation"]


def test_assess_unknown_service_is_insufficient(client, doc_id):
    body = client.post("/api/coverage/assess",
                       json={"service_name": "Tattoo removal", "document_id": doc_id}).json()
    assert body["classification"] == "insufficient_information"
    assert body["citations"] == []
    assert body["recommended_steps"]


def test_auth_checklist_includes_policy_requirements(client, doc_id):
    body = client.post("/api/coverage/auth-checklist",
                       json={"service_name": "MRI", "document_id": doc_id}).json()
    assert body["policy_document_id"] == doc_id
    assert body["readiness"] == "missing_information"
    descriptions = {i["description"] for i in body["items"]}
    assert "CPT/HCPCS code for MRI" in descriptions
    assert "Letter of Medical Necessity from treating provider" in descriptions
    assert body["missing_count"] == sum(1 for i in body["items"] if i["required"])
    assert body["citations"]


def test_coverage_requires_document_id(client):
    assert client.post("/api/coverage/assess", json={"service_name": "MRI"}).status_code == 422


# ── Disclaimers ──────────────────────────────────────────────────────

def _every_endpoint(client, doc_id):
    with POLICY_PDF.open("rb") as f:
        upload = client.post("/api/policies/upload",
                             files={"file": ("p.pdf", f, "application/pdf")})
    return {
        "health": client.get("/api/health"),
        "dashboard": client.get("/api/dashboard"),
        "policies": client.get("/api/policies"),
        "policy": client.get(f"/api/policies/{doc_id}"),
        "summary": client.get(f"/api/policies/{doc_id}/summary"),
        "chunks": client.get(f"/api/policies/{doc_id}/chunks"),
        "upload": upload,
        "chat": client.post("/api/chat", json={"question": "Is acupuncture covered?"}),
        "assess": client.post("/api/coverage/assess",
                              json={"service_name": "MRI", "document_id": doc_id}),
        "checklist": client.post("/api/coverage/auth-checklist",
                                 json={"service_name": "MRI", "document_id": doc_id}),
        "not_found": client.get("/api/policies/nope"),
    }


def test_every_api_response_has_disclaimer_header(client, doc_id):
    for name, resp in _every_endpoint(client, doc_id).items():
        assert resp.headers.get("X-Disclaimer") == DISCLAIMER, name


def test_object_responses_have_disclaimer_field(client, doc_id):
    responses = _every_endpoint(client, doc_id)
    # bare-list and single-record (registry) responses rely on the header
    for name in ("health", "dashboard", "summary", "chunks", "upload",
                 "chat", "assess", "checklist"):
        assert responses[name].json()["disclaimer"] == DISCLAIMER, name


def test_disclaimer_is_not_written_into_registry(client, data_dirs, doc_id):
    _every_endpoint(client, doc_id)
    assert "disclaimer" not in (data_dirs["policies"] / "_registry.json").read_text()
