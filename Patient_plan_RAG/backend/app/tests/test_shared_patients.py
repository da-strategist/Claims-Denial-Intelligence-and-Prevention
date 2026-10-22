"""Sharing a policy gives the provider a patient record for the person, so
they appear in the patient list and pickers, and questions about them are
answered from what they shared. Duplicates can be merged."""

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.auth.users import Role
from backend.app.services import records, sharing
from backend.app.tests.conftest import POLICY_PDF, sign_in

SUMMIT = POLICY_PDF.parent / "summit_care_silver_hmo_2026.pdf"


def _upload(client, path=POLICY_PDF, **form):
    with path.open("rb") as f:
        r = client.post("/api/policies/upload", data=form, files={"file": (path.name, f, "application/pdf")})
    assert r.status_code == 200, r.text
    return r.json()["document_id"]


@pytest.fixture
def w(client):
    if not SUMMIT.exists():
        pytest.skip("summit policy missing")
    general = records.orgs.add(records.Org(records.new_id(), "General Hospital"))
    mercy = records.orgs.add(records.Org(records.new_id(), "Mercy Medical"))
    w = {"general": general.org_id, "mercy": mercy.org_id}
    w["staff"] = sign_in(TestClient(main.app), "gs@general.example", Role.HOSPITAL_STAFF, general.org_id)
    w["mstaff"] = sign_in(TestClient(main.app), "ms@mercy.example", Role.HOSPITAL_STAFF, mercy.org_id)
    w["alice"] = sign_in(TestClient(main.app), "alice@example.com")
    w["alice"].patch("/api/me/profile", json={"full_name": "Alice Smith"})
    w["apex"], w["summit"] = _upload(w["alice"]), _upload(w["alice"], SUMMIT)
    return w


def _share(w, doc="apex", org="general"):
    r = w["alice"].post("/api/shares", json={"document_id": w[doc], "org_id": w[org]})
    assert r.status_code == 200, r.text
    return r.json()["share_id"]


def _alice_record(w, who="staff"):
    [p] = [p for p in w[who].get("/api/hospital/patients").json() if p["linked_username"] == "alice@example.com"]
    return p


def test_sharing_creates_a_patient_record_with_the_policy(w):
    _share(w)
    p = _alice_record(w)
    assert (p["name"], p["linked_username"]) == ("Alice Smith", "alice@example.com")
    assert [d["document_id"] for d in p["documents"]] == [w["apex"]]
    # a second policy goes to the same record
    _share(w, "summit")
    assert {d["document_id"] for d in _alice_record(w)["documents"]} == {w["apex"], w["summit"]}
    assert len(w["staff"].get("/api/hospital/patients").json()) == 1
    # sharing also connected Alice to the provider
    assert [x["name"] for x in w["alice"].get("/api/me/providers").json()] == ["General Hospital"]
    # each provider gets its own record; other providers see nothing
    assert w["mstaff"].get("/api/hospital/patients").json() == []
    _share(w, "apex", "mercy")
    assert _alice_record(w, "mstaff")["patient_id"] != _alice_record(w)["patient_id"]


def test_chat_about_the_patient_answers_from_what_they_shared(w):
    _share(w, "summit")
    pid = _alice_record(w)["patient_id"]
    r = w["staff"].post("/api/chat", json={"question": "What is the deductible?", "patient_id": pid})
    assert r.status_code == 200, r.text
    cited = {c["document_id"] for c in r.json()["citations"]}
    assert cited == {w["summit"]}  # never Alice's unshared Apex policy
    s = w["staff"].get("/api/chat/suggestions", params={"patient_id": pid})
    assert s.status_code == 200 and s.json()["questions"]


def test_stopping_sharing_empties_the_record_but_keeps_it(w):
    share = _share(w)
    pid = _alice_record(w)["patient_id"]
    w["alice"].delete(f"/api/shares/{share}")
    p = w["staff"].get(f"/api/hospital/patients/{pid}").json()
    assert p["documents"] == []
    r = w["staff"].post("/api/chat", json={"question": "What is the deductible?", "patient_id": pid})
    assert r.json()["citations"] == []


def test_sharing_again_restores_an_archived_record(w):
    _share(w)
    pid = _alice_record(w)["patient_id"]
    w["staff"].patch(f"/api/hospital/patients/{pid}", json={"archived": True})
    _share(w, "summit")
    assert _alice_record(w)["patient_id"] == pid  # same record, back in the list


def test_a_deleted_record_is_recreated_by_the_next_share(w):
    _share(w)
    old = _alice_record(w)["patient_id"]
    w["staff"].delete(f"/api/hospital/patients/{old}")
    _share(w, "summit")
    new = _alice_record(w)
    assert new["patient_id"] != old
    assert [d["document_id"] for d in new["documents"]] == [w["summit"]]


def test_merging_a_duplicate_into_the_staff_record(w):
    staff_pid = w["staff"].post("/api/hospital/patients", json={"name": "Alice Smith", "reference": "MRN-7"}).json()["patient_id"]
    upload = _upload(w["staff"], SUMMIT, patient_id=staff_pid)
    _share(w)
    auto = _alice_record(w)["patient_id"]
    items = [{"item_id": "1", "category": "form", "description": "Form", "required": True, "completed": False}]
    w["staff"].post(f"/api/hospital/patients/{auto}/checklists",
                    json={"document_id": w["apex"], "service_name": "MRI", "items": items}).raise_for_status()

    r = w["staff"].post(f"/api/hospital/patients/{auto}/merge", json={"into_patient_id": staff_pid})
    assert r.status_code == 200, r.text
    merged = r.json()
    assert (merged["reference"], merged["linked_username"]) == ("MRN-7", "alice@example.com")
    assert {d["document_id"] for d in merged["documents"]} == {upload, w["apex"]}
    assert w["staff"].get(f"/api/hospital/patients/{auto}").status_code == 404
    assert [c["service_name"] for c in w["staff"].get(f"/api/hospital/patients/{staff_pid}/checklists").json()] == ["MRI"]
    # later shares follow the merged record
    _share(w, "summit")
    assert w["summit"] in {d["document_id"] for d in _alice_record(w)["documents"]}
    assert _alice_record(w)["patient_id"] == staff_pid


def test_merge_is_limited_to_the_providers_own_records(w):
    _share(w)
    auto = _alice_record(w)["patient_id"]
    assert w["staff"].post(f"/api/hospital/patients/{auto}/merge",
                           json={"into_patient_id": auto}).status_code == 400
    mercy_pid = w["mstaff"].post("/api/hospital/patients", json={"name": "M"}).json()["patient_id"]
    assert w["staff"].post(f"/api/hospital/patients/{auto}/merge",
                           json={"into_patient_id": mercy_pid}).status_code == 404
    assert w["mstaff"].post(f"/api/hospital/patients/{auto}/merge",
                            json={"into_patient_id": mercy_pid}).status_code == 404


def test_attaching_the_connection_elsewhere_moves_the_shared_policies(w):
    _share(w)
    auto = _alice_record(w)["patient_id"]
    staff_pid = w["staff"].post("/api/hospital/patients", json={"name": "A. Smith"}).json()["patient_id"]
    [conn] = w["staff"].get("/api/hospital/connections").json()
    w["staff"].patch(f"/api/hospital/connections/{conn['connection_id']}", json={"patient_id": staff_pid})
    assert [d["document_id"] for d in w["staff"].get(f"/api/hospital/patients/{staff_pid}").json()["documents"]] == [w["apex"]]
    assert w["staff"].get(f"/api/hospital/patients/{auto}").json()["documents"] == []


def test_startup_backfill_files_older_shares_once(w):
    # a share made before records were automatic: no patient, no connection
    old = records.shares.add(records.Share(records.new_id(), w["apex"], w["general"], "alice@example.com"))
    assert sharing.backfill() == 1
    pid = records.shares.get(old.share_id).patient_id
    assert records.patients.get(pid).linked_username == "alice@example.com"
    # staff later unfile it: the next startup leaves that decision alone
    records.shares.update(old.share_id, patient_id=None)
    assert sharing.backfill() == 0
    assert records.shares.get(old.share_id).patient_id is None


def test_backfill_skips_providers_that_are_not_approved(w):
    records.orgs.update(w["general"], status=records.PENDING)
    records.shares.add(records.Share(records.new_id(), w["apex"], w["general"], "alice@example.com"))
    assert sharing.backfill() == 0
    assert records.patients.all() == []


def test_sharing_links_a_typed_entry_with_the_same_name(w):
    typed = w["alice"].post("/api/me/providers", json={"name": "general hospital", "phone": "555 1"}).json()
    _share(w)
    [entry] = w["alice"].get("/api/me/providers").json()
    assert (entry["provider_id"], entry["name"], entry["on_platform"], entry["phone"]) == (
        typed["provider_id"], "General Hospital", True, "555 1")


def test_a_record_named_after_the_email_takes_the_name_given_later(w):
    w["alice"].patch("/api/me/profile", json={"full_name": ""})
    _share(w)
    assert _alice_record(w)["name"] == "alice@example.com"  # no name to use yet
    w["alice"].patch("/api/me/profile", json={"full_name": "Alice Smith"})
    assert _alice_record(w)["name"] == "Alice Smith"
    # a name staff typed is theirs: later profile changes leave it alone
    pid = _alice_record(w)["patient_id"]
    w["staff"].patch(f"/api/hospital/patients/{pid}", json={"name": "Alice M. Smith"})
    w["alice"].patch("/api/me/profile", json={"full_name": "Ali"})
    assert _alice_record(w)["name"] == "Alice M. Smith"


def test_startup_renames_records_left_with_an_email(w):
    _share(w)
    pid = _alice_record(w)["patient_id"]
    records.patients.update(pid, name="alice@example.com")  # made before the profile had a name
    assert sharing.refresh_names() == 1
    assert _alice_record(w)["name"] == "Alice Smith"
    assert sharing.refresh_names() == 0
