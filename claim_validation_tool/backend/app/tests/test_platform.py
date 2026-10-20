"""Platform administration: organisations, their first admins, suspension, and emergency
(break-glass) access — read-only, time-limited, with a reason, in the organisation's log."""

from datetime import UTC, datetime, timedelta

from app.data.audit import get_audit_log, get_platform_audit_log
from app.data.emergency import get_emergency_access
from app.models import Role
from app.tests.conftest import TestClient, sign_in
from app.tests.test_claim_entry import NEW_CLAIM

REASON = "Ticket 4471: claims page fails to load for the billing team"


def emergency(client, org="lakeside", reason=REASON, minutes=60):
    return client.post(f"/api/platform/organisations/{org}/emergency-access", json={"reason": reason, "minutes": minutes})


def test_platform_accounts_see_no_organisations_data(client):
    sign_in(client, Role.PLATFORM)
    me = client.get("/api/auth/me").json()
    assert (me["organisation"], me["permissions"]) == (None, ["platform:manage"])
    for path in ("/api/claims", "/api/patients", "/api/dashboard", "/api/users", "/api/audit"):
        assert client.get(path).status_code == 403, path
    orgs = client.get("/api/platform/organisations").json()
    assert [(o["id"], o["accounts"], o["active_admins"]) for o in orgs] == [("lakeside", 3, 1), ("meridian", 3, 1)]


def test_organisation_admins_have_no_platform_powers(client):
    assert client.get("/api/platform/organisations").status_code == 403
    assert emergency(client).status_code == 403
    # …and can't create or promote platform accounts
    body = {"username": "sneaky", "display_name": "S", "role": "platform", "password": "Sneaky-pass-123"}
    assert client.post("/api/users", json=body).status_code == 422
    assert client.patch("/api/users/biller1", json={"role": "platform"}).status_code == 422
    # Platform accounts are in no organisation, so no organisation lists them
    assert "platform1" not in {u["username"] for u in client.get("/api/users").json()}


def test_a_new_organisation_starts_empty_with_its_first_admin(client):
    sign_in(client, Role.PLATFORM)
    res = client.post("/api/platform/organisations", json={"id": "acme", "name": "Acme Health"})
    assert res.status_code == 201 and res.json()["accounts"] == 0
    assert client.post("/api/platform/organisations", json={"id": "acme", "name": "Again"}).status_code == 409
    admin = client.post("/api/platform/organisations/acme/admins", json={
        "username": "acmeadmin", "display_name": "Acme Admin", "password": "Acme-admin-123",
    })
    assert admin.status_code == 201 and admin.json()["role"] == "admin"
    with TestClient(client.app) as acme:
        acme.post("/api/auth/login", json={"username": "acmeadmin", "password": "Acme-admin-123"})
        assert acme.get("/api/auth/me").json()["organisation"] == {"id": "acme", "name": "Acme Health"}
        assert acme.get("/api/claims").json()["total"] == 0
        assert acme.get("/api/dashboard").status_code == 200
        assert acme.get("/api/codes/procedures").json()  # shared code sets are there


def test_suspending_an_organisation_locks_its_accounts_out(client):
    sign_in(client, Role.BILLER, "lakeside")
    assert client.get("/api/claims").status_code == 200
    with TestClient(client.app) as platform:
        sign_in(platform, Role.PLATFORM)
        assert platform.post("/api/platform/organisations/lakeside/suspend").json()["status"] == "suspended"
        assert client.get("/api/claims").status_code == 401  # signed out at once
        with TestClient(client.app) as fresh:
            res = fresh.post("/api/auth/login", json={"username": "admin2", "password": "Fixture-password-1"})
            assert res.status_code == 403 and "suspended" in res.text
        platform.post("/api/platform/organisations/lakeside/reactivate")
    sign_in(client, Role.BILLER, "lakeside")
    assert client.get("/api/claims").status_code == 200


def test_emergency_access_is_read_only_audited_and_visible_to_the_organisation(client, today):
    sign_in(client, Role.PLATFORM)
    assert emergency(client, reason="just looking").status_code == 422  # needs a real reason
    assert emergency(client, minutes=600).status_code == 422  # four hours at most
    grant = emergency(client).json()

    # Looking works, as Lakeside, read-only
    me = client.get("/api/auth/me").json()
    assert me["organisation"]["id"] == "lakeside" and me["emergency"]["reason"] == REASON
    assert client.get("/api/claims").json()["total"] == 10
    assert client.get("/api/claims/CLM9000001").status_code == 200
    assert client.get("/api/claims/CLM0000001").status_code == 404  # still only Lakeside
    assert client.post("/api/claims", json={**NEW_CLAIM, "patient_id": "PAT900001"}).status_code == 403
    assert client.patch("/api/rules/RULE-001", json={"enabled": False}).status_code == 403
    assert client.get("/api/users").status_code == 403
    assert client.get("/api/platform/organisations").status_code == 200  # still the platform

    # Lakeside's own log has the grant, its reason, and what was looked at
    events = get_audit_log("lakeside").events()
    started = next(e for e in events if e.action == "EMERGENCY ACCESS STARTED")
    assert (started.username, started.detail["reason"]) == ("platform1", REASON)
    looked = [e for e in events if e.action == "GET /api/claims/{claim_id}"]
    assert looked[0].detail == {"emergency_access": grant["id"]} and looked[0].role == "platform"
    assert not any(e.username == "platform1" for e in get_audit_log("meridian").events())
    # Platform work itself stays in the platform log
    assert any(e.action.startswith("POST /api/platform/") for e in get_platform_audit_log().events())

    # Lakeside's admins see it and can end it
    sign_in(client, Role.ADMIN, "lakeside")
    (listed,) = client.get("/api/audit/emergency-access").json()
    assert listed["reason"] == REASON and listed["ended_at"] is None
    ended = client.post(f"/api/audit/emergency-access/{grant['id']}/end").json()
    assert ended["ended_by"] == "admin2"
    sign_in(client, Role.ADMIN)  # Meridian can't see or end Lakeside's
    assert client.get("/api/audit/emergency-access").json() == []
    assert client.post(f"/api/audit/emergency-access/{grant['id']}/end").status_code == 404

    sign_in(client, Role.PLATFORM)
    assert client.get("/api/claims").status_code == 403  # access is over
    assert client.get("/api/auth/me").json()["organisation"] is None


def test_emergency_access_expires(client):
    sign_in(client, Role.PLATFORM)
    grant = emergency(client, minutes=15).json()
    assert client.get("/api/claims").status_code == 200
    store = get_emergency_access()
    for g in store.all():
        if g.id == grant["id"]:
            g.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert client.get("/api/claims").status_code == 403


def test_emergency_access_needs_an_active_organisation(client):
    sign_in(client, Role.PLATFORM)
    client.post("/api/platform/organisations/lakeside/suspend")
    assert emergency(client).status_code == 409
