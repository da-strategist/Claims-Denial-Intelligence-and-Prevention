"""Saved drafts: unfinished New Claim forms, kept apart from claims."""

import json
from datetime import UTC, datetime, timedelta

from app.data.audit import get_audit_log
from app.data.drafts import DraftStore
from app.models import DraftForm, Role
from app.tests.conftest import sign_in

# Only a patient and one half-typed diagnosis: far from a valid claim
PARTIAL = {"patient_id": "PAT000003", "diagnoses": ["E11"], "lines": [{"cpt_code": "", "dx": 0}]}


def save(client, form=PARTIAL):
    res = client.post("/api/drafts", json=form)
    assert res.status_code == 201, res.text
    return res.json()


def test_an_incomplete_form_can_be_saved_and_reopened(client):
    draft = save(client)
    assert draft["id"].startswith("DRF-")
    assert draft["created_by"] == draft["updated_by"] == "admin1"
    assert draft["form"]["payer_id"] is None and draft["form"]["service_date"] is None

    opened = client.get(f"/api/drafts/{draft['id']}").json()
    assert opened["form"]["diagnoses"] == ["E11"]
    assert opened["form"]["billing"]["policy"]["relationship"] == "self"  # defaults filled in
    assert opened["patient"]["patient_id"] == "PAT000003"  # resolved for the form's picker


def test_drafts_are_not_claims(client):
    total = client.get("/api/claims").json()["total"]
    save(client)
    assert client.get("/api/claims").json()["total"] == total
    assert client.get("/api/claims", params={"status": "Draft"}).json()["total"] == 0


def test_list_shows_newest_first_with_the_patient(client):
    first = save(client)
    second = save(client, {**PARTIAL, "lines": [{"cpt_code": "99213", "dx": 0}]})
    rows = client.get("/api/drafts").json()
    assert [r["id"] for r in rows] == [second["id"], first["id"]]
    assert rows[0]["patient_name"] == "Donald Davis"
    assert (rows[0]["lines"], rows[1]["lines"]) == (1, 0)


def test_saving_again_updates_the_draft_and_its_expiry(client):
    draft = save(client)
    sign_in(client, Role.BILLER)  # shared with everyone who can enter claims
    res = client.put(f"/api/drafts/{draft['id']}", json={**PARTIAL, "payer_id": "PAY001"})
    assert res.status_code == 200, res.text
    updated = res.json()
    assert (updated["created_by"], updated["updated_by"]) == ("admin1", "biller1")
    assert updated["form"]["payer_id"] == "PAY001"
    assert updated["expires_at"] > draft["expires_at"]


def test_delete(client):
    draft = save(client)
    assert client.delete(f"/api/drafts/{draft['id']}").status_code == 204
    assert client.get(f"/api/drafts/{draft['id']}").status_code == 404
    assert client.delete(f"/api/drafts/{draft['id']}").status_code == 404


def test_fields_keep_their_formats(client):
    for form in (
        {"patient_id": "PAT000999"},  # not registered
        {"patient_id": "not-a-patient"},
        {"payer_id": "PAY1"},
        {"diagnoses": ["x" * 13]},
        {"diagnoses": [""] * 13},
        {"lines": [{"dx": 99}]},
        {"billing": {"policy": {"member_id": "x" * 31}}},
        {"billing": {"other_policies": [{}, {}, {}]}},
    ):
        assert client.post("/api/drafts", json=form).status_code == 422, form


def test_only_roles_that_enter_claims_see_drafts(client):
    save(client)
    sign_in(client, Role.ANALYST)
    assert client.get("/api/drafts").status_code == 403
    assert client.post("/api/drafts", json=PARTIAL).status_code == 403


def test_saving_and_opening_are_audited(client):
    draft = save(client)
    client.get(f"/api/drafts/{draft['id']}")
    events = [e for e in get_audit_log().events() if "/api/drafts" in e.action]
    assert [(e.action, e.records) for e in events] == [
        ("POST /api/drafts", {"draft_id": draft["id"], "patient_id": "PAT000003"}),
        ("GET /api/drafts/{draft_id}", {"draft_id": draft["id"], "patient_id": "PAT000003"}),
    ]


def test_drafts_expire_after_30_days(tmp_path):
    path = tmp_path / "drafts.json"
    store = DraftStore(path)
    old = store.create(DraftForm(), "a")
    fresh = store.create(DraftForm(), "a")
    assert old.expires_at - old.updated_at == timedelta(days=30)
    assert path.stat().st_mode & 0o777 == 0o600

    # Age one past its expiry on disk; reopening the store drops it, file included
    data = json.loads(path.read_text())
    for item in data["drafts"]:
        if item["id"] == old.id:
            item["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    path.write_text(json.dumps(data))
    reopened = DraftStore(path)
    assert [d.id for d in reopened.list()] == [fresh.id]
    assert old.id not in path.read_text()
