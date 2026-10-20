"""Individual accounts: overview, profile, providers, sharing, policy
management, export, sign out everywhere, account deletion."""

import json

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.auth.users import Role, user_store
from backend.app.services import records, registry
from backend.app.tests.conftest import POLICY_PDF, sign_in

SUMMIT = POLICY_PDF.parent / "summit_care_silver_hmo_2026.pdf"


def _upload(client, path, name):
    with path.open("rb") as f:
        r = client.post("/api/policies/upload", files={"file": (name, f, "application/pdf")})
    assert r.status_code == 200, r.text
    return r.json()["document_id"]


@pytest.fixture
def world(client, data_dirs):
    if not SUMMIT.exists():
        pytest.skip("summit policy missing")
    general = records.orgs.add(records.Org(records.new_id(), "General Hospital"))
    mercy = records.orgs.add(records.Org(records.new_id(), "Mercy Medical"))
    alice = sign_in(TestClient(main.app), "alice@example.com")
    w = {"admin": client, "alice": alice, "general": general.org_id, "mercy": mercy.org_id,
         "dirs": data_dirs,
         "apex": _upload(alice, POLICY_PDF, "apex.pdf"), "summit": _upload(alice, SUMMIT, "summit.pdf")}
    w["gstaff"] = sign_in(TestClient(main.app), "gs@general.example", Role.HOSPITAL_STAFF, general.org_id)
    w["mstaff"] = sign_in(TestClient(main.app), "ms@mercy.example", Role.HOSPITAL_STAFF, mercy.org_id)
    w["bob"] = sign_in(TestClient(main.app), "bob@example.com")
    for doc, org in (("apex", general), ("summit", general), ("apex", mercy)):
        alice.post("/api/shares", json={"document_id": w[doc], "org_id": org.org_id}).raise_for_status()
    return w


# ── Overview ─────────────────────────────────────────────────────────

def test_overview_groups_insurance_by_company(world):
    o = world["alice"].get("/api/me/overview").json()
    insurers = {g["insurer"]: g["plans"] for g in o["insurance"]}
    assert set(insurers) == {"Apex Health Insurance", "Summit Care Health Plan, Inc."}
    apex = insurers["Apex Health Insurance"][0]
    assert (apex["plan_name"], apex["plan_id"], apex["expiration_date"]) == \
        ("Gold PPO Plan", "AHI-GOLD-2025-PPO", "2025-12-31")
    assert apex["expired"] is True  # ended 2025-12-31
    assert insurers["Summit Care Health Plan, Inc."][0]["expired"] is False
    assert o["policy_count"] == 2 and o["profile"]["username"] == "alice@example.com"


def test_overview_is_for_individuals_only(world):
    for who in ("gstaff", "admin"):
        assert world[who].get("/api/me/overview").status_code == 403


# ── Profile and providers ────────────────────────────────────────────

def test_profile_update(world):
    r = world["alice"].patch("/api/me/profile", json={"full_name": " Alice Smith ", "phone": "+1 555 0100"})
    assert (r.json()["full_name"], r.json()["phone"]) == ("Alice Smith", "+1 555 0100")
    assert world["alice"].patch("/api/me/profile", json={"phone": "call me!"}).status_code == 422


def test_providers_are_private_to_their_owner(world):
    w = world
    p = w["alice"].post("/api/me/providers", json={"name": "Dr. Lee", "kind": "doctor",
                                                   "phone": "555 0101", "notes": "GP"}).json()
    assert [x["name"] for x in w["alice"].get("/api/me/providers").json()] == ["Dr. Lee"]
    assert w["bob"].get("/api/me/providers").json() == []
    assert w["bob"].patch(f"/api/me/providers/{p['provider_id']}", json={"name": "x"}).status_code == 404
    assert w["bob"].delete(f"/api/me/providers/{p['provider_id']}").status_code == 404
    upd = w["alice"].patch(f"/api/me/providers/{p['provider_id']}", json={"name": "Dr. Lee", "kind": "clinic"})
    assert upd.json()["kind"] == "clinic"
    assert w["alice"].post("/api/me/providers", json={"name": "X", "kind": "astrologer"}).status_code == 422
    assert w["alice"].delete(f"/api/me/providers/{p['provider_id']}").status_code == 200
    assert w["alice"].get("/api/me/providers").json() == []


# ── Sharing overview ─────────────────────────────────────────────────

def test_sharing_overview_and_removing_a_hospital(world):
    w = world
    sharing = {h["org_name"]: {p["document_id"] for p in h["policies"]}
               for h in w["alice"].get("/api/me/sharing").json()}
    assert sharing == {"General Hospital": {w["apex"], w["summit"]}, "Mercy Medical": {w["apex"]}}
    assert w["gstaff"].get(f"/api/policies/{w['summit']}").status_code == 200
    r = w["alice"].delete(f"/api/me/sharing/{w['general']}")
    assert r.json()["revoked"] == 2
    for doc in ("apex", "summit"):
        assert w["gstaff"].get(f"/api/policies/{w[doc]}").status_code == 404
    assert w["mstaff"].get(f"/api/policies/{w['apex']}").status_code == 200  # Mercy untouched
    assert w["alice"].delete(f"/api/me/sharing/{w['general']}").status_code == 404
    assert w["bob"].delete(f"/api/me/sharing/{w['mercy']}").status_code == 404  # not Bob's shares


# ── Rename / delete a policy ─────────────────────────────────────────

def test_rename_policy(world):
    w = world
    r = w["alice"].patch(f"/api/policies/{w['apex']}", json={"display_name": "  Work plan "})
    assert r.json()["display_name"] == "Work plan"
    assert w["bob"].patch(f"/api/policies/{w['apex']}", json={"display_name": "x"}).status_code == 404
    # a hospital can read a shared policy but not change it
    assert w["gstaff"].patch(f"/api/policies/{w['apex']}", json={"display_name": "x"}).status_code == 403


def test_delete_policy_removes_file_index_and_shares(world):
    w = world
    entry = next(e for e in registry.load() if e["document_id"] == w["apex"])
    assert (w["dirs"]["uploads"] / entry["filename"]).exists()
    assert w["gstaff"].delete(f"/api/policies/{w['apex']}").status_code == 403
    assert w["alice"].delete(f"/api/policies/{w['apex']}").status_code == 200
    assert w["alice"].get(f"/api/policies/{w['apex']}").status_code == 404
    assert not (w["dirs"]["uploads"] / entry["filename"]).exists()
    assert not (w["dirs"]["chunks"] / f"{w['apex']}.json").exists()
    assert all(s.document_id != w["apex"] for s in records.shares.all())
    assert w["mstaff"].get(f"/api/policies/{w['apex']}").status_code == 404


def test_preloaded_samples_cannot_be_deleted_from_the_app(world, doc_id):
    assert world["admin"].delete(f"/api/policies/{doc_id}").status_code == 403
    assert world["alice"].delete(f"/api/policies/{doc_id}").status_code == 403


# ── Export, sign out everywhere, delete account ──────────────────────

def test_export_contains_my_data_only(world):
    w = world
    w["alice"].post("/api/me/providers", json={"name": "Dr. Lee"})
    data = w["alice"].get("/api/me/export").json()
    assert {p["document_id"] for p in data["policies"]} == {w["apex"], w["summit"]}
    assert [p["name"] for p in data["providers"]] == ["Dr. Lee"]
    assert len(data["sharing"]) == 2 and "password_hash" not in json.dumps(data)
    assert w["gstaff"].get("/api/me/export").status_code == 403


def test_sign_out_everywhere(world):
    other = sign_in(TestClient(main.app), "alice@example.com")
    assert world["alice"].post("/api/me/sign-out-everywhere").status_code == 200
    assert world["alice"].get("/api/auth/me").status_code == 401
    assert other.get("/api/auth/me").status_code == 401


def test_delete_account_requires_typing_the_email(world):
    assert world["alice"].request("DELETE", "/api/me", json={"confirm_email": "wrong@example.com"}).status_code == 400
    assert user_store.get("alice@example.com") is not None


def test_delete_account_removes_everything_and_hospitals_lose_access(world, isolated_audit_log):
    w = world
    w["alice"].post("/api/me/providers", json={"name": "Dr. Lee"})
    r = w["alice"].request("DELETE", "/api/me", json={"confirm_email": "Alice@Example.com"})
    assert r.status_code == 200
    assert user_store.get("alice@example.com") is None
    assert not [e for e in registry.load() if e.get("owner") == "alice@example.com"]
    assert not [s for s in records.shares.all() if s.shared_by == "alice@example.com"]
    assert not [p for p in records.providers.all() if p.owner == "alice@example.com"]
    assert list(w["dirs"]["uploads"].iterdir()) == []
    for who in ("gstaff", "mstaff"):
        assert w[who].get(f"/api/policies/{w['apex']}").status_code == 404
    assert w["alice"].get("/api/auth/me").status_code == 401
    entries = [json.loads(line) for line in isolated_audit_log.read_text().splitlines()]
    deletion = next(e for e in entries if (e["method"], e["route"]) == ("DELETE", "/api/me"))
    assert (deletion["user"], deletion["target"], deletion["status"]) == \
        ("alice@example.com", "alice@example.com", 200)
    # the email can be registered again from scratch
    again = TestClient(main.app).post("/api/auth/register", json={
        "username": "alice@example.com", "password": "a brand new passphrase"})
    assert again.status_code == 200


# ── Chat suggestions endpoint and next steps ─────────────────────────

def test_starter_questions_come_from_my_plans(world):
    qs = world["alice"].get("/api/chat/suggestions").json()["questions"]
    assert qs[0] == "Which of my plans has the lower deductible?"
    assert any("Gold PPO Plan" in q for q in qs) and any("Silver HMO Value" in q for q in qs)
    one = world["alice"].get("/api/chat/suggestions", params={"policy_id": world["summit"]}).json()
    assert all("Gold PPO" not in q for q in one["questions"])
    assert world["bob"].get("/api/chat/suggestions", params={"policy_id": world["apex"]}).status_code == 404


def test_chat_answer_carries_grounded_next_steps(world):
    body = world["alice"].post("/api/chat", json={"question": "Is an MRI covered?",
                                                  "policy_id": world["apex"]}).json()
    [step] = body["next_steps"]
    assert "prior authorization" in step["text"]
    assert step["document_id"] == world["apex"] and step["page_number"]
    assert body["follow_up_suggestions"][0] == "What does my provider need to submit for prior authorization?"
