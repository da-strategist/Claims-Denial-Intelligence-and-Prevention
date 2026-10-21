"""Platform admin: account search/detail, deleting spam and rejected
sign-ups, read-only provider details, dashboard stats, audit log, security
events and sample health."""

import json

import pytest
from fastapi.testclient import TestClient

from backend.app import audit, main
from backend.app.auth.users import Role, user_store
from backend.app.services import records, registry
from backend.app.tests.conftest import POLICY_PDF, TEST_PASSWORD, sign_in


def _upload(client):
    with POLICY_PDF.open("rb") as f:
        r = client.post("/api/policies/upload", files={"file": ("p.pdf", f, "application/pdf")})
    assert r.status_code == 200, r.text
    return r.json()["document_id"]


@pytest.fixture
def w(client):
    general = records.orgs.add(records.Org(records.new_id(), "General Hospital", city="Springfield",
                                           address="1 Main St", npi="1234567893"))
    w = {"admin": client, "general": general.org_id}
    w["staff"] = sign_in(TestClient(main.app), "gs@general.example", Role.HOSPITAL_STAFF, general.org_id)
    w["alice"] = sign_in(TestClient(main.app), "alice@example.com")
    w["doc"] = _upload(w["alice"])
    w["alice"].post("/api/shares", json={"document_id": w["doc"], "org_id": general.org_id}).raise_for_status()
    return w


def _reject_sign_up(w, name="Fake Care", email="f@fake.example"):
    c = TestClient(main.app)
    r = c.post("/api/auth/register/provider", json={
        "org_name": name, "category": "other", "city": "X", "full_name": "F",
        "username": email, "password": TEST_PASSWORD})
    org_id = r.json()["org_id"]
    w["admin"].post(f"/api/admin/orgs/{org_id}/reject", json={"note": "Not real"}).raise_for_status()
    return org_id


# ── Accounts ─────────────────────────────────────────────────────────

def test_sign_in_records_last_sign_in_and_admin_sees_pending_count(w):
    users = {u["username"]: u for u in w["admin"].get("/api/admin/users").json()}
    assert users["alice@example.com"]["last_sign_in"] and users["alice@example.com"]["created_at"]
    assert users["gs@general.example"]["org_name"] == "General Hospital"
    assert w["admin"].get("/api/auth/me").json()["pending_providers"] == 0
    TestClient(main.app).post("/api/auth/register/provider", json={
        "org_name": "New Clinic", "category": "clinic", "city": "Y", "full_name": "N",
        "username": "n@new.example", "password": TEST_PASSWORD})
    assert w["admin"].get("/api/auth/me").json()["pending_providers"] == 1
    assert "pending_providers" not in w["alice"].get("/api/auth/me").json()


def test_account_detail_shows_counts_never_documents(w):
    d = w["admin"].get("/api/admin/users/alice@example.com").json()
    assert d["holds"] == {"policies": 1, "shares": 1, "providers": 1, "connected_providers": 1}
    assert w["doc"] not in json.dumps(d) and "password_hash" not in json.dumps(d)
    assert w["admin"].get("/api/admin/users/nobody@example.com").status_code == 404


def test_deleting_a_spam_individual(w):
    r = w["admin"].request("DELETE", "/api/admin/users/alice@example.com", json={"confirm": "alice@"})
    assert r.status_code == 400
    r = w["admin"].request("DELETE", "/api/admin/users/alice@example.com", json={"confirm": "Alice@Example.com"})
    assert r.status_code == 200
    assert user_store.get("alice@example.com") is None
    assert not [e for e in registry.load() if e.get("owner") == "alice@example.com"]
    assert records.shares.all() == [] and records.providers.all() == []
    assert w["alice"].get("/api/auth/me").status_code == 401
    assert w["staff"].get(f"/api/policies/{w['doc']}").status_code == 404
    # the provider's patient record stays, without the policy
    [p] = w["staff"].get("/api/hospital/patients").json()
    assert p["documents"] == []


def test_only_individuals_can_be_deleted_by_the_admin(w):
    for who in ("gs@general.example", "admin@example.com"):
        r = w["admin"].request("DELETE", f"/api/admin/users/{who}", json={"confirm": who})
        assert r.status_code == 400
    assert user_store.get("gs@general.example") is not None


# ── Providers ────────────────────────────────────────────────────────

def test_provider_detail_is_read_only(w):
    d = w["admin"].get(f"/api/admin/orgs/{w['general']}").json()
    assert (d["name"], d["address"], d["npi"], d["category_label"]) == (
        "General Hospital", "1 Main St", "1234567893", "Hospital")
    assert [s["username"] for s in d["staff"]] == ["gs@general.example"]
    assert (d["connection_count"], d["share_count"]) == (1, 1)
    # renaming is not possible: only access (disable) can change
    w["admin"].patch(f"/api/admin/orgs/{w['general']}", json={"name": "Renamed"})
    assert records.orgs.get(w["general"]).name == "General Hospital"


def test_deleting_a_rejected_sign_up(w):
    org_id = _reject_sign_up(w)
    # an individual's providers list points at it (written directly: it was never approved)
    records.providers.add(records.Provider(records.new_id(), "alice@example.com", "Fake Care", "other",
                                           org_id=org_id))
    assert w["admin"].request("DELETE", f"/api/admin/orgs/{org_id}", json={"confirm": "fake care"}).status_code == 400
    r = w["admin"].request("DELETE", f"/api/admin/orgs/{org_id}", json={"confirm": "Fake Care"})
    assert r.status_code == 200
    assert records.orgs.get(org_id) is None and user_store.get("f@fake.example") is None
    # the individual keeps the entry, now as a typed one
    entry = next(p for p in records.providers.all() if p.name == "Fake Care")
    assert (entry.org_id, entry.owner) == (None, "alice@example.com")


def test_approved_and_pending_providers_cannot_be_deleted(w):
    r = w["admin"].request("DELETE", f"/api/admin/orgs/{w['general']}", json={"confirm": "General Hospital"})
    assert r.status_code == 400
    c = TestClient(main.app)
    pending = c.post("/api/auth/register/provider", json={
        "org_name": "Wait", "category": "other", "city": "X", "full_name": "W",
        "username": "w@wait.example", "password": TEST_PASSWORD}).json()["org_id"]
    assert w["admin"].request("DELETE", f"/api/admin/orgs/{pending}", json={"confirm": "Wait"}).status_code == 400


# ── Oversight ────────────────────────────────────────────────────────

def test_dashboard_stats(w):
    w["alice"].post("/api/chat", json={"question": "What is the deductible?"}).raise_for_status()
    _reject_sign_up(w)
    s = w["admin"].get("/api/admin/stats").json()
    assert len(s["weeks"]) == 8
    assert s["accounts"]["individuals"] == 1 and s["accounts"]["provider_staff"] == 2
    assert s["providers"]["by_status"] == {"active": 1, "rejected": 1}
    assert s["providers"]["by_category"] == {"Hospital": 1}
    assert s["sign_ups"]["individuals"][-1] == 1
    assert s["activity"]["questions"][-1] == 1 and s["activity"]["uploads"][-1] == 1
    assert s["totals"]["shares"] == 1 and s["totals"]["patient_records"] == 1
    assert s["totals"]["individual_policies"] == 1 and s["totals"]["samples"] >= 1


def test_audit_log_filters_and_verify(w):
    w["staff"].get("/api/hospital/patients")
    w["alice"].get("/api/hospital/patients")  # 403
    log = w["admin"].get("/api/admin/audit", params={"user": "alice"}).json()
    assert log["total"] >= 1 and all("alice" in e["user"] for e in log["entries"])
    refused = w["admin"].get("/api/admin/audit", params={"status": "403"}).json()["entries"]
    assert [(e["user"], e["route"]) for e in refused] == [("alice@example.com", "/api/hospital/patients")]
    by_org = w["admin"].get("/api/admin/audit", params={"org_id": w["general"], "include_routine": True}).json()["entries"]
    assert by_org and {e["user"] for e in by_org} == {"gs@general.example"}
    assert all(set(e) == {"ts", "user", "role", "method", "route", "document_id", "patient_id",
                          "target", "status", "client", "label", "routine"} for e in by_org)
    # plain words; routine page loads only on request
    entries = w["admin"].get("/api/admin/audit").json()["entries"]
    assert not any(e["routine"] for e in entries)
    assert "Uploaded a policy" in {e["label"] for e in entries}
    assert "Loaded hospital/patients" not in {e["label"] for e in entries if e["status"] == 200}
    everything = w["admin"].get("/api/admin/audit", params={"include_routine": True}).json()
    assert any(e["routine"] for e in everything["entries"])
    page = w["admin"].get("/api/admin/audit", params={"limit": 2, "include_routine": True}).json()
    assert len(page["entries"]) == 2 and page["total"] > 2
    assert w["admin"].get("/api/admin/audit/verify").json()["ok"] is True
    # a tampered line is reported
    lines = audit.AUDIT_FILE.read_text().splitlines()
    lines[0] = lines[0].replace('"status": 200', '"status": 201')
    audit.AUDIT_FILE.write_text("\n".join(lines) + "\n")
    v = w["admin"].get("/api/admin/audit/verify").json()
    assert v["ok"] is False and "chain broken" in v["problem"]


def test_security_events(w):
    c = TestClient(main.app)
    for _ in range(5):
        c.post("/api/auth/login", json={"username": "alice@example.com", "password": "wrong password"})
    c.post("/api/auth/login", json={"username": "alice@example.com", "password": "wrong password"})  # locked
    w["alice"].get("/api/admin/users")  # 403
    _reject_sign_up(w)
    s = w["admin"].get("/api/admin/security").json()
    assert s["failed_sign_ins"][0]["user"] == "alice@example.com" and s["failed_sign_ins"][0]["count"] == 5
    assert s["lockouts"][0]["count"] == 1
    assert [r["user"] for r in s["refused_requests"]] == ["alice@example.com"]
    assert [r["name"] for r in s["rejected_sign_ups"]] == ["Fake Care"]


def test_sample_health_and_reprocess(w, doc_id):
    [sample] = [s for s in w["admin"].get("/api/admin/samples").json() if s["document_id"] == doc_id]
    assert sample["healthy"] and sample["chunk_count"] > 0 and sample["page_count"] > 0
    assert "insurer_name" in sample["metadata_found"]
    # an individual's own policy is not a sample
    assert w["doc"] not in {s["document_id"] for s in w["admin"].get("/api/admin/samples").json()}
    r = w["admin"].post(f"/api/admin/samples/{doc_id}/reprocess")
    assert r.status_code == 200 and r.json()["healthy"]
    assert w["admin"].post(f"/api/admin/samples/{w['doc']}/reprocess").status_code == 404


@pytest.mark.parametrize("path", ["/api/admin/stats", "/api/admin/audit", "/api/admin/audit/verify",
                                  "/api/admin/security", "/api/admin/samples",
                                  "/api/admin/users/alice@example.com"])
def test_oversight_is_platform_admin_only(w, path):
    for who in ("alice", "staff"):
        assert w[who].get(path).status_code == 403
