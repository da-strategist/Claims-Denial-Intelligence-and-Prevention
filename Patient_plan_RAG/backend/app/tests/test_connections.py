"""An individual adds a provider that is on the platform: the provider sees
the connection (name and email only, never policies unless shared), can
attach it to a patient record, and shares then file themselves."""

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.auth.users import Role
from backend.app.services import records
from backend.app.tests.conftest import POLICY_PDF, sign_in


def _upload(client, **form):
    with POLICY_PDF.open("rb") as f:
        r = client.post("/api/policies/upload", data=form, files={"file": ("p.pdf", f, "application/pdf")})
    assert r.status_code == 200, r.text
    return r.json()["document_id"]


@pytest.fixture
def w(client):
    general = records.orgs.add(records.Org(records.new_id(), "General Hospital", city="Springfield"))
    lab = records.orgs.add(records.Org(records.new_id(), "Quick Labs", category="laboratory"))
    waiting = records.orgs.add(records.Org(records.new_id(), "Waiting Clinic", status=records.PENDING))
    w = {"general": general.org_id, "lab": lab.org_id, "waiting": waiting.org_id}
    w["staff"] = sign_in(TestClient(main.app), "gs@general.example", Role.HOSPITAL_STAFF, general.org_id)
    w["lab_staff"] = sign_in(TestClient(main.app), "ls@lab.example", Role.HOSPITAL_STAFF, lab.org_id)
    w["alice"] = sign_in(TestClient(main.app), "alice@example.com")
    w["alice"].patch("/api/me/profile", json={"full_name": "Alice Smith"})
    w["doc"] = _upload(w["alice"])
    return w


def _connect(w, org="general"):
    r = w["alice"].post("/api/me/providers", json={"org_id": w[org], "notes": "cardiology"})
    assert r.status_code == 200, r.text
    return r.json()


def test_adding_a_platform_provider_connects_without_sharing(w):
    row = _connect(w)
    assert (row["name"], row["kind"], row["on_platform"], row["city"], row["notes"]) == (
        "General Hospital", "hospital", True, "Springfield", "cardiology")
    assert "patient_id" not in row
    conns = w["staff"].get("/api/hospital/connections").json()
    assert [(c["name"], c["email"], c["shared_count"], c["is_new"], c["patient_id"]) for c in conns] == [
        ("Alice Smith", "alice@example.com", 0, True, None)]
    # no policies come with the connection
    assert w["staff"].get("/api/hospital/shared").json() == []
    assert w["staff"].get(f"/api/policies/{w['doc']}").status_code == 404
    # other providers see nothing
    assert w["lab_staff"].get("/api/hospital/connections").json() == []
    assert w["lab_staff"].patch(f"/api/hospital/connections/{row['provider_id']}",
                                json={"patient_id": None}).status_code == 404


def test_category_becomes_the_kind(w):
    assert _connect(w, "lab")["kind"] == "laboratory"


def test_only_approved_providers_once_each(w):
    _connect(w)
    r = w["alice"].post("/api/me/providers", json={"org_id": w["general"]})
    assert r.status_code == 400 and "already in your providers" in r.json()["detail"]
    assert w["alice"].post("/api/me/providers", json={"org_id": w["waiting"]}).status_code == 404
    assert w["alice"].post("/api/me/providers", json={"org_id": "nosuchorg"}).status_code == 404
    assert w["alice"].post("/api/me/providers", json={"name": " "}).status_code == 400


def test_a_typed_entry_can_be_linked(w):
    typed = w["alice"].post("/api/me/providers", json={"name": "general hosp", "kind": "doctor",
                                                       "phone": "555 1"}).json()
    assert typed["on_platform"] is False and typed["org_id"] is None
    assert w["staff"].get("/api/hospital/connections").json() == []
    linked = w["alice"].patch(f"/api/me/providers/{typed['provider_id']}",
                              json={"org_id": w["general"], "phone": "555 1"}).json()
    assert (linked["name"], linked["kind"], linked["on_platform"], linked["phone"]) == (
        "General Hospital", "hospital", True, "555 1")
    assert len(w["staff"].get("/api/hospital/connections").json()) == 1
    # a linked entry keeps the provider's own name
    again = w["alice"].patch(f"/api/me/providers/{typed['provider_id']}",
                             json={"name": "Renamed", "notes": "n"}).json()
    assert (again["name"], again["notes"]) == ("General Hospital", "n")


def test_attaching_to_a_patient_files_shares_now_and_later(w):
    conn = _connect(w)["provider_id"]
    first = w["alice"].post("/api/shares", json={"document_id": w["doc"], "org_id": w["general"]}).json()
    pid = w["staff"].post("/api/hospital/patients", json={"name": "Alice Smith"}).json()["patient_id"]
    r = w["staff"].patch(f"/api/hospital/connections/{conn}", json={"patient_id": pid})
    assert r.status_code == 200
    assert records.shares.get(first["share_id"]).patient_id == pid
    row = w["staff"].get("/api/hospital/connections").json()[0]
    assert (row["patient_name"], row["shared_count"], row["is_new"]) == ("Alice Smith", 1, False)
    # a policy shared later goes straight under the patient
    second_doc = _upload(w["alice"])
    second = w["alice"].post("/api/shares", json={"document_id": second_doc, "org_id": w["general"]}).json()
    assert records.shares.get(second["share_id"]).patient_id == pid
    patient = w["staff"].get(f"/api/hospital/patients/{pid}").json()
    assert {d["document_id"] for d in patient["documents"]} == {w["doc"], second_doc}
    # the individual never sees the provider's patient record ID
    assert all("patient_id" not in p for p in w["alice"].get("/api/me/providers").json())
    # attaching to another provider's patient is refused
    other = w["lab_staff"].post("/api/hospital/patients", json={"name": "X"}).json()["patient_id"]
    assert w["staff"].patch(f"/api/hospital/connections/{conn}", json={"patient_id": other}).status_code == 404


def test_overview_lists_unattached_connections(w):
    _connect(w)
    o = w["staff"].get("/api/hospital/overview").json()
    assert [c["email"] for c in o["unlinked_connections"]] == ["alice@example.com"]


def test_removing_the_provider_ends_the_connection_not_the_shares(w):
    conn = _connect(w)["provider_id"]
    w["alice"].post("/api/shares", json={"document_id": w["doc"], "org_id": w["general"]})
    assert w["alice"].delete(f"/api/me/providers/{conn}").status_code == 200
    assert w["staff"].get("/api/hospital/connections").json() == []
    assert len(w["staff"].get("/api/hospital/shared").json()) == 1


def test_deleting_the_patient_detaches_the_connection(w):
    conn = _connect(w)["provider_id"]
    pid = w["staff"].post("/api/hospital/patients", json={"name": "Alice"}).json()["patient_id"]
    w["staff"].patch(f"/api/hospital/connections/{conn}", json={"patient_id": pid})
    w["staff"].delete(f"/api/hospital/patients/{pid}")
    assert w["staff"].get("/api/hospital/connections").json()[0]["patient_id"] is None


def test_deleting_the_account_ends_the_connection(w):
    _connect(w)
    w["alice"].request("DELETE", "/api/me", json={"confirm_email": "alice@example.com"})
    assert w["staff"].get("/api/hospital/connections").json() == []


def test_a_disabled_provider_shows_as_off_platform(w):
    _connect(w)
    records.orgs.update(w["general"], disabled=True)
    assert w["alice"].get("/api/me/providers").json()[0]["on_platform"] is False
