"""Pilot requests: the website's form saves them, and the Platform page approves or declines
them. Only platform accounts see them, and they're encrypted and audited."""

from datetime import UTC, datetime, timedelta

from app.data.audit import get_platform_audit_log
from app.data.orgs import get_org_registry
from app.data.pilot_requests import PER_EMAIL_PER_DAY, PER_ADDRESS_PER_DAY, get_pilot_requests
from app.models import Role
from app.tests.conftest import TestClient, sign_in

FORM = {
    "name": "Grace Adeyemi",
    "email": "Grace.Adeyemi@valleyhospital.org",
    "organization": "Valley Critical Access Hospital",
    "title": "Revenue cycle director",
    "org_type": "Critical Access Hospital",
    "message": "We bill about 900 claims a month.",
}
REQUESTS = "/api/platform/pilot-requests"


def submit(client, **changes):
    return client.post("/api/pilot-requests", json={**FORM, **changes})


def organisation(org_id="valley", username="gadeyemi"):
    return {
        "organisation": {
            "id": org_id,
            "name": "Valley Critical Access Hospital",
            "admin": {"username": username, "display_name": "Grace Adeyemi", "password": "Valley-temp-123"},
        }
    }


def only_request(client):
    [request] = client.get(REQUESTS).json()
    return request


def test_anyone_can_ask_and_the_platform_sees_it_pending(anon_client):
    res = submit(anon_client)
    assert res.status_code == 202 and res.json() == {"received": True}
    platform = sign_in(anon_client, Role.PLATFORM)
    request = only_request(platform)
    assert request["status"] == "pending"
    assert request["email"] == "grace.adeyemi@valleyhospital.org"
    assert request["organization"] == "Valley Critical Access Hospital"


def test_only_platform_accounts_see_requests(anon_client):
    submit(anon_client)
    assert anon_client.get(REQUESTS).status_code == 401
    admin = sign_in(anon_client, Role.ADMIN)
    assert admin.get(REQUESTS).status_code == 403
    assert admin.post(f"{REQUESTS}/PR-x/decline", json={"reason": "No"}).status_code == 403


def test_the_form_checks_its_fields(anon_client):
    assert submit(anon_client, email="not-an-email").status_code == 422
    assert submit(anon_client, name="   ").status_code == 422
    assert submit(anon_client, message="x" * 1501).status_code == 422


def test_a_filled_hidden_field_is_answered_but_not_kept(anon_client):
    assert submit(anon_client, website="http://spam.example").status_code == 202
    assert get_pilot_requests().all() == []


def test_one_address_or_email_cant_flood_the_list(anon_client):
    for _ in range(PER_EMAIL_PER_DAY):
        assert submit(anon_client).status_code == 202
    assert submit(anon_client).status_code == 429
    for n in range(PER_ADDRESS_PER_DAY - PER_EMAIL_PER_DAY):
        assert submit(anon_client, email=f"other{n}@valleyhospital.org").status_code == 202
    assert submit(anon_client, email="new@valleyhospital.org").status_code == 429  # same address


def test_approving_creates_the_organisation_and_its_first_admin(anon_client):
    submit(anon_client)
    platform = sign_in(anon_client, Role.PLATFORM)
    request_id = only_request(platform)["id"]
    res = platform.post(f"{REQUESTS}/{request_id}/approve", json=organisation())
    assert res.status_code == 200, res.text
    assert (res.json()["id"], res.json()["active_admins"]) == ("valley", 1)
    decided = only_request(platform)
    assert decided["status"] == "approved" and decided["organisation_id"] == "valley"
    assert decided["decided_by"] == "platform1"
    assert platform.post(f"{REQUESTS}/{request_id}/approve", json=organisation("valley2", "grace2")).status_code == 409
    with TestClient(anon_client.app) as grace:
        me = grace.post("/api/auth/login", json={"username": "gadeyemi", "password": "Valley-temp-123"}).json()
        assert me["must_change_password"] is True  # the temporary password, as for any new admin


def test_a_failed_approval_leaves_the_request_pending(anon_client):
    submit(anon_client)
    platform = sign_in(anon_client, Role.PLATFORM)
    request_id = only_request(platform)["id"]
    taken = platform.post(f"{REQUESTS}/{request_id}/approve", json=organisation(username="admin1"))
    assert taken.status_code == 409
    assert only_request(platform)["status"] == "pending"
    assert get_org_registry().get("valley") is None


def test_declining_keeps_the_reason(anon_client):
    submit(anon_client)
    platform = sign_in(anon_client, Role.PLATFORM)
    request_id = only_request(platform)["id"]
    assert platform.post(f"{REQUESTS}/{request_id}/decline", json={"reason": ""}).status_code == 422
    res = platform.post(f"{REQUESTS}/{request_id}/decline", json={"reason": "Outside the US for now"})
    assert res.status_code == 200
    assert (res.json()["status"], res.json()["decline_reason"]) == ("declined", "Outside the US for now")
    assert platform.post(f"{REQUESTS}/{request_id}/approve", json=organisation()).status_code == 409
    assert platform.post(f"{REQUESTS}/PR-none/decline", json={"reason": "Spam"}).status_code == 404


def test_requests_are_encrypted_and_audited_by_id(anon_client):
    submit(anon_client)
    stored = get_pilot_requests().path.read_bytes()
    assert b"Adeyemi" not in stored and b"valleyhospital" not in stored
    platform = sign_in(anon_client, Role.PLATFORM)
    request_id = only_request(platform)["id"]
    platform.post(f"{REQUESTS}/{request_id}/decline", json={"reason": "Not a hospital"})
    events = get_platform_audit_log().events()
    submitted = next(e for e in events if e.action == "POST /api/pilot-requests")
    assert submitted.detail["pilot_request"] == request_id
    assert "Adeyemi" not in submitted.model_dump_json()
    assert any(e.action == "GET /api/platform/pilot-requests" for e in events)
    declined = next(e for e in events if e.action.endswith("/decline"))
    assert declined.records["request_id"] == request_id and declined.username == "platform1"


def test_decided_requests_are_deleted_after_a_year(anon_client):
    submit(anon_client)
    submit(anon_client, email="later@valleyhospital.org")
    store = get_pilot_requests()
    first, second = store.all()
    store.decline(first.id, "platform1", "Not now")
    store._requests[first.id] = store._requests[first.id].model_copy(
        update={"decided_at": datetime.now(UTC) - timedelta(days=366)}
    )
    assert [r.id for r in store.all()] == [second.id]  # the pending one stays however old
