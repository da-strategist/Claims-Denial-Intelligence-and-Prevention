"""Provider self sign-up, the pending state, and the platform admin's
approval queue (approve, reject, create directly)."""

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.services import records
from backend.app.tests.conftest import POLICY_PDF, TEST_PASSWORD, sign_in

SIGN_UP = {
    "org_name": "Lakeside Clinic", "category": "clinic", "npi": "1234567893",
    "address": "2 Lake Rd", "city": "Riverton", "phone": "555 0101",
    "full_name": "Dana Lee", "username": "Dana@Lakeside.example", "password": TEST_PASSWORD,
}


def _sign_up(**changes) -> tuple[TestClient, object]:
    c = TestClient(main.app)
    return c, c.post("/api/auth/register/provider", json=SIGN_UP | changes)


def _upload(client, **form):
    with POLICY_PDF.open("rb") as f:
        return client.post("/api/policies/upload", data=form,
                           files={"file": ("p.pdf", f, "application/pdf")})


@pytest.fixture
def pending(client):
    """A provider that signed itself up, plus an individual with a policy."""
    dana, r = _sign_up()
    assert r.status_code == 200, r.text
    alice = sign_in(TestClient(main.app), "alice@example.com")
    doc = _upload(alice).json()["document_id"]
    return {"admin": client, "dana": dana, "org_id": r.json()["org_id"], "alice": alice, "doc": doc}


def test_sign_up_creates_a_pending_provider_and_signs_in(pending):
    me = pending["dana"].get("/api/auth/me").json()
    assert (me["username"], me["role"], me["full_name"]) == ("dana@lakeside.example", "hospital_admin", "Dana Lee")
    assert (me["org_name"], me["org_category"], me["org_status"]) == ("Lakeside Clinic", "clinic", "pending")
    assert me["must_change_password"] is False
    org = records.orgs.get(pending["org_id"])
    assert (org.npi, org.city, org.contact_email, org.signed_up_by) == (
        "1234567893", "Riverton", "dana@lakeside.example", "dana@lakeside.example")


def test_pending_provider_can_do_nothing_until_approved(pending):
    dana = pending["dana"]
    for path in ("/api/hospital/overview", "/api/hospital/patients", "/api/policies"):
        r = dana.get(path)
        assert r.status_code == 403 and "awaiting approval" in r.json()["detail"]
    assert dana.post("/api/hospital/patients", json={"name": "P"}).status_code == 403
    assert _upload(dana).status_code == 403
    # individuals can't find it or share with it
    assert pending["alice"].get("/api/shares/hospitals").json() == []
    r = pending["alice"].post("/api/shares", json={"document_id": pending["doc"], "org_id": pending["org_id"]})
    assert r.status_code == 404


def test_approval_opens_the_provider(pending):
    admin, dana = pending["admin"], pending["dana"]
    queue = admin.get("/api/admin/orgs").json()
    assert queue[0]["org_id"] == pending["org_id"] and queue[0]["status"] == "pending"
    assert (queue[0]["signed_up_by_name"], queue[0]["npi"], queue[0]["category"]) == ("Dana Lee", "1234567893", "clinic")

    r = admin.post(f"/api/admin/orgs/{pending['org_id']}/approve", json={"note": "NPI checked"})
    assert r.status_code == 200 and r.json()["status"] == "active"
    assert (r.json()["reviewed_by"], r.json()["review_note"]) == ("admin@example.com", "NPI checked")
    assert admin.post(f"/api/admin/orgs/{pending['org_id']}/approve", json={}).status_code == 400

    # the same session works now, and individuals see and can share with it
    assert dana.get("/api/auth/me").json()["org_status"] == "active"
    assert dana.get("/api/hospital/patients").status_code == 200
    listed = pending["alice"].get("/api/shares/hospitals").json()
    assert [(h["name"], h["category_label"], h["city"]) for h in listed] == [
        ("Lakeside Clinic", "Clinic or physician practice", "Riverton")]
    r = pending["alice"].post("/api/shares", json={"document_id": pending["doc"], "org_id": pending["org_id"]})
    assert r.status_code == 200


def test_rejection_signs_the_provider_out_and_explains(pending):
    admin, dana = pending["admin"], pending["dana"]
    r = admin.post(f"/api/admin/orgs/{pending['org_id']}/reject", json={"note": "Could not verify the NPI"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert dana.get("/api/auth/me").status_code == 401
    r = TestClient(main.app).post("/api/auth/login", json={"username": "dana@lakeside.example",
                                                           "password": TEST_PASSWORD})
    assert r.status_code == 403
    assert "not approved" in r.json()["detail"] and "Could not verify the NPI" in r.json()["detail"]
    # a mistaken rejection can be reversed
    assert admin.post(f"/api/admin/orgs/{pending['org_id']}/approve", json={}).status_code == 200
    r = TestClient(main.app).post("/api/auth/login", json={"username": "dana@lakeside.example",
                                                           "password": TEST_PASSWORD})
    assert r.status_code == 200 and r.json()["org_status"] == "active"


def test_only_pending_sign_ups_can_be_rejected(client):
    r = client.post("/api/admin/orgs", json={"name": "General Hospital", "admin_username": "ga@general.example"})
    assert client.post(f"/api/admin/orgs/{r.json()['org_id']}/reject", json={}).status_code == 400


def test_only_the_platform_admin_reviews(pending):
    for who in ("dana", "alice"):
        assert pending[who].post(f"/api/admin/orgs/{pending['org_id']}/approve", json={}).status_code == 403
    assert pending["admin"].post("/api/admin/orgs/nosuchorg/approve", json={}).status_code == 404


@pytest.mark.parametrize("changes, status", [
    ({"category": "spa"}, 400),
    ({"npi": "12345"}, 422),
    ({"city": ""}, 422),
    ({"full_name": ""}, 422),
    ({"username": "not-an-email"}, 400),
    ({"password": "short"}, 400),
])
def test_sign_up_validation_leaves_no_orphan_provider(data_dirs, changes, status):
    _, r = _sign_up(**changes)
    assert r.status_code == status
    assert records.orgs.all() == []


def test_sign_up_with_an_existing_email_is_refused(data_dirs):
    sign_in(TestClient(main.app), "dana@lakeside.example")
    _, r = _sign_up()
    assert r.status_code == 400 and "already exists" in r.json()["detail"]
    assert records.orgs.all() == []


def test_npi_is_optional(data_dirs):
    _, r = _sign_up(npi="")
    assert r.status_code == 200


def test_admin_created_provider_is_active_with_its_category(client):
    r = client.post("/api/admin/orgs", json={"name": "Main St Pharmacy", "admin_username": "rx@main.example",
                                             "category": "pharmacy", "city": "Riverton"})
    assert r.status_code == 200
    assert (r.json()["status"], r.json()["category"], r.json()["city"]) == ("active", "pharmacy", "Riverton")
    assert client.post("/api/admin/orgs", json={"name": "Day Spa", "admin_username": "x@x.example",
                                                "category": "spa"}).status_code == 400


def test_existing_organisations_load_as_active_hospitals(data_dirs):
    """Records written before provider sign-up have no category or status."""
    import json
    records.orgs.path.write_text(json.dumps([{"org_id": "old1", "name": "Old Hospital",
                                              "disabled": False, "created_at": "2026-01-01"}]))
    org = records.orgs.get("old1")
    assert (org.category, org.status, org.usable) == ("hospital", "active", True)
