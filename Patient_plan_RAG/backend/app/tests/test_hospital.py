"""Hospital accounts: patient records, insurance summary, saved checklists,
shared-policy filing, overview, hospital profile, access log, wording."""

import datetime as real_dt

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.auth.users import Role
from backend.app.routers import hospital
from backend.app.services import records, registry
from backend.app.tests.conftest import POLICY_PDF, sign_in

SUMMIT = POLICY_PDF.parent / "summit_care_silver_hmo_2026.pdf"
QUESTION = "I have stage 2 diabetes — is an MRI covered?"


def _upload(client, path, name, **form):
    with path.open("rb") as f:
        r = client.post("/api/policies/upload", data=form, files={"file": (name, f, "application/pdf")})
    assert r.status_code == 200, r.text
    return r.json()["document_id"]


@pytest.fixture
def world(client, data_dirs):
    if not SUMMIT.exists():
        pytest.skip("summit policy missing")
    general = records.orgs.add(records.Org(records.new_id(), "General Hospital"))
    mercy = records.orgs.add(records.Org(records.new_id(), "Mercy Medical"))
    w = {"admin": client, "dirs": data_dirs, "general": general.org_id, "mercy": mercy.org_id}
    w["gadmin"] = sign_in(TestClient(main.app), "ga@general.example", Role.HOSPITAL_ADMIN, general.org_id)
    w["gstaff"] = sign_in(TestClient(main.app), "gs@general.example", Role.HOSPITAL_STAFF, general.org_id)
    w["madmin"] = sign_in(TestClient(main.app), "ma@mercy.example", Role.HOSPITAL_ADMIN, mercy.org_id)
    w["alice"] = sign_in(TestClient(main.app), "alice@example.com")
    w["alice"].patch("/api/me/profile", json={"full_name": "Alice Smith"})
    w["p1"] = w["gstaff"].post("/api/hospital/patients", json={"name": "Pat One", "reference": "MRN-1"}).json()["patient_id"]
    w["apex_doc"] = _upload(w["gstaff"], POLICY_PDF, "apex.pdf", patient_id=w["p1"])     # ended 2025-12-31
    w["summit_doc"] = _upload(w["gstaff"], SUMMIT, "summit.pdf", patient_id=w["p1"])     # 2026 plan
    w["alice_doc"] = _upload(w["alice"], SUMMIT, "alice.pdf")
    w["share"] = w["alice"].post("/api/shares", json={"document_id": w["alice_doc"],
                                                      "org_id": general.org_id}).json()["share_id"]
    return w


def _patient(w, who="gstaff", pid=None):
    return w[who].get(f"/api/hospital/patients/{pid or w['p1']}")


# ── H1 patient records ───────────────────────────────────────────────

def test_edit_patient_details(world):
    r = world["gstaff"].patch(f"/api/hospital/patients/{world['p1']}",
                              json={"name": " Pat Onee ", "reference": "MRN-9", "date_of_birth": "1980-02-03"})
    assert (r.json()["name"], r.json()["reference"], r.json()["date_of_birth"]) == ("Pat Onee", "MRN-9", "1980-02-03")
    assert world["gstaff"].patch(f"/api/hospital/patients/{world['p1']}",
                                 json={"date_of_birth": "03/02/1980"}).status_code == 422
    assert world["madmin"].patch(f"/api/hospital/patients/{world['p1']}", json={"name": "x"}).status_code == 404


def test_archive_hides_patient_from_list_and_restore(world):
    w = world
    w["gstaff"].patch(f"/api/hospital/patients/{w['p1']}", json={"archived": True})
    assert w["gstaff"].get("/api/hospital/patients").json() == []
    archived = w["gstaff"].get("/api/hospital/patients", params={"include_archived": True}).json()
    assert [p["archived"] for p in archived] == [True]
    assert _patient(w).status_code == 200  # still reachable directly
    w["gstaff"].patch(f"/api/hospital/patients/{w['p1']}", json={"archived": False})
    assert len(w["gstaff"].get("/api/hospital/patients").json()) == 1


def test_insurance_summary_per_patient(world):
    docs = {d["document_id"]: d for d in _patient(world).json()["documents"]}
    apex = docs[world["apex_doc"]]
    assert (apex["insurer_name"], apex["plan_id"], apex["coverage_status"]) == \
        ("Apex Health Insurance", "AHI-GOLD-2025-PPO", "ended")
    assert docs[world["summit_doc"]]["coverage_status"] in ("active", "ended")  # date-dependent; 2026 plan


def test_delete_patient_removes_hospital_documents_but_only_unfiles_shares(world):
    w = world
    w["gstaff"].patch(f"/api/hospital/shared/{w['share']}", json={"patient_id": w["p1"]})
    w["gstaff"].post(f"/api/hospital/patients/{w['p1']}/checklists", json={
        "document_id": w["apex_doc"], "service_name": "MRI", "items": []}).raise_for_status()
    assert w["madmin"].delete(f"/api/hospital/patients/{w['p1']}").status_code == 404
    r = w["gstaff"].delete(f"/api/hospital/patients/{w['p1']}")
    assert r.json()["documents_deleted"] == 2
    assert _patient(w).status_code == 404
    ids = {e["document_id"] for e in registry.load()}
    assert w["apex_doc"] not in ids and w["summit_doc"] not in ids
    assert w["alice_doc"] in ids                       # the patient's own policy survives
    assert records.shares.get(w["share"]).patient_id is None  # unfiled, still shared
    assert w["gstaff"].get(f"/api/policies/{w['alice_doc']}").status_code == 200
    assert records.checklists.all() == []


# ── H2 saved checklists ──────────────────────────────────────────────

ITEMS = [{"item_id": "proc-1", "category": "procedure", "description": "CPT code", "required": True},
         {"item_id": "clin-1", "category": "clinical", "description": "Clinical notes", "required": True}]


def test_save_update_and_delete_a_checklist(world):
    w = world
    url = f"/api/hospital/patients/{w['p1']}/checklists"
    saved = w["gstaff"].post(url, json={"document_id": w["summit_doc"], "service_name": "MRI",
                                        "service_code": "70551", "items": ITEMS}).json()
    assert saved["created_by"] == "gs@general.example" and len(saved["items"]) == 2
    items = [{**ITEMS[0], "completed": True}, ITEMS[1]]
    upd = w["gadmin"].patch(f"{url}/{saved['checklist_id']}", json={"items": items}).json()
    assert upd["items"][0]["completed"] is True
    assert [c["service_name"] for c in w["gstaff"].get(url).json()] == ["MRI"]
    assert w["madmin"].get(url).status_code == 404
    assert w["alice"].get(url).status_code == 403
    assert w["gstaff"].delete(f"{url}/{saved['checklist_id']}").status_code == 200
    assert w["gstaff"].get(url).json() == []


def test_checklist_must_use_one_of_the_patients_documents(world):
    w = world
    other = w["gstaff"].post("/api/hospital/patients", json={"name": "Other"}).json()["patient_id"]
    r = w["gstaff"].post(f"/api/hospital/patients/{other}/checklists",
                         json={"document_id": w["apex_doc"], "service_name": "MRI", "items": []})
    assert r.status_code == 404


# ── H3 shared policies, overview, profile, access log ────────────────

def test_shared_list_shows_sharer_name_and_new_flag(world):
    w = world
    [row] = w["gstaff"].get("/api/hospital/shared").json()
    assert (row["shared_by_name"], row["is_new"], row["insurer_name"]) == \
        ("Alice Smith", True, "Summit Care Health Plan, Inc.")
    w["gstaff"].patch(f"/api/hospital/shared/{w['share']}", json={"patient_id": w["p1"]})
    assert w["gstaff"].get("/api/hospital/shared").json()[0]["is_new"] is False


class _FixedDate(real_dt.date):
    @classmethod
    def today(cls):
        return cls(2026, 12, 10)


def test_overview_lists_ended_and_ending_plans_and_unfiled_shares(world, monkeypatch):
    monkeypatch.setattr(hospital, "date", _FixedDate)
    o = world["gstaff"].get("/api/hospital/overview").json()
    assert o["patient_count"] == 1
    assert [r["document_id"] for r in o["plans_ended"]] == [world["apex_doc"]]
    assert [r["document_id"] for r in o["plans_ending_soon"]] == [world["summit_doc"]]  # ends 2026-12-31
    assert o["plans_ending_soon"][0]["patient_name"] == "Pat One"
    assert [s["share_id"] for s in o["unfiled_shares"]] == [world["share"]]
    assert world["alice"].get("/api/hospital/overview").status_code == 403


def test_hospital_profile_is_set_by_its_admin_and_shown_to_individuals(world):
    w = world
    body = {"address": "1 Main St", "city": "Springfield", "phone": "+1 555 0100",
            "contact_email": "desk@general.example"}
    assert w["gstaff"].patch("/api/hospital/profile", json=body).status_code == 403
    assert w["gadmin"].patch("/api/hospital/profile", json={**body, "contact_email": "nope"}).status_code == 422
    assert w["gadmin"].patch("/api/hospital/profile", json=body).json()["city"] == "Springfield"
    assert w["gstaff"].get("/api/hospital/profile").json()["address"] == "1 Main St"
    directory = {h["name"]: h for h in w["alice"].get("/api/shares/hospitals").json()}
    assert directory["General Hospital"]["city"] == "Springfield"


def test_access_log_shows_own_staff_activity_without_question_text(world):
    w = world
    w["gstaff"].get(f"/api/hospital/patients/{w['p1']}")
    w["gstaff"].post("/api/chat", json={"question": QUESTION, "patient_id": w["p1"]})
    w["madmin"].get("/api/hospital/patients")
    log = w["gadmin"].get("/api/hospital/access-log").json()
    users = {r["user"] for r in log}
    assert "gs@general.example" in users and "ma@mercy.example" not in users
    chat = next(r for r in log if r["route"] == "/api/chat")
    assert (chat["patient_id"], chat["patient_name"]) == (w["p1"], "Pat One")
    assert "diabetes" not in str(log)
    assert log == sorted(log, key=lambda r: r["ts"], reverse=True)
    assert w["gstaff"].get("/api/hospital/access-log").status_code == 403


# ── H4 wording for hospital staff ────────────────────────────────────

def test_hospital_staff_get_staff_wording(world):
    w = world
    body = w["gstaff"].post("/api/chat", json={"question": "Is an MRI covered?",
                                               "patient_id": w["p1"], "policy_id": w["summit_doc"]}).json()
    assert body["next_steps"][0]["text"].startswith("Request prior authorization before scheduling")
    assert body["follow_up_suggestions"][0] == "What documentation does the prior authorization request need?"
    starters = w["gstaff"].get("/api/chat/suggestions", params={"patient_id": w["p1"]}).json()["questions"]
    assert starters[0] == "Which of the patient's plans has the lower deductible?"
    assert not any(" my " in f" {q} " for q in starters)


def test_individuals_keep_member_wording(world):
    body = world["alice"].post("/api/chat", json={"question": "Is an MRI covered?",
                                                  "policy_id": world["alice_doc"]}).json()
    assert body["next_steps"][0]["text"].startswith("Ask your provider to request prior authorization")
