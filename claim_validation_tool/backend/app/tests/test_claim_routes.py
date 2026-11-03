"""The two ways a claim leaves: handed off to the hospital's billing system, or submitted
from here. A claim takes one route, so the payer can't receive it twice."""

from datetime import date

from app.data import repository
from app.data.audit import get_audit_log
from app.data.new_claims import get_new_claim_store
from app.data.repository import ClaimsRepository
from app.models import AuditQuery, Role
from app.tests.conftest import sign_in
from app.tests.test_claim_entry import create, submit


def hand_off(client, claim_id, **body):
    return client.post(f"/api/claims/{claim_id}/hand-off", json=body)


def reopen(client, claim_id, confirmed=True):
    return client.post(f"/api/claims/{claim_id}/reopen", json={"confirmed_not_sent": confirmed})


def flagged_draft(client) -> str:
    """A draft with an open error: prior auth required, not obtained."""
    return create(client, pa_required=True).json()["claim"]["claim_id"]


def test_a_clean_claim_is_handed_off_with_no_837(client, today):
    claim_id = create(client).json()["claim"]["claim_id"]
    res = hand_off(client, claim_id)
    assert res.status_code == 200, res.text
    claim = res.json()["claim"]
    assert claim["status"] == "Handed off"
    assert claim["edi"] is None
    assert claim["handoff"]["open_issues"] == []
    assert claim["handoff"]["handed_off_by"]


def test_open_issues_must_be_acknowledged_and_are_kept(client, today):
    claim_id = flagged_draft(client)
    refused = hand_off(client, claim_id)
    assert refused.status_code == 422
    assert "RULE-002" in refused.json()["detail"]
    assert client.get(f"/api/claims/{claim_id}").json()["status"] == "Draft"

    res = hand_off(client, claim_id, acknowledge_open_issues=True)
    assert res.status_code == 200, res.text
    assert any("RULE-002" in issue for issue in res.json()["claim"]["handoff"]["open_issues"])


def test_sending_from_here_is_still_blocked_by_open_issues(client, today):
    assert submit(client, flagged_draft(client)).status_code == 422


def test_a_handed_off_claim_cannot_also_be_submitted(client, today):
    claim_id = create(client).json()["claim"]["claim_id"]
    hand_off(client, claim_id)
    res = submit(client, claim_id)
    assert res.status_code == 409
    assert "twice" in res.json()["detail"]
    assert client.get(f"/api/claims/{claim_id}").json()["edi"] is None


def test_a_submitted_claim_cannot_be_handed_off_or_reopened(client, today):
    claim_id = create(client).json()["claim"]["claim_id"]
    assert submit(client, claim_id).status_code == 200
    assert hand_off(client, claim_id).status_code == 409
    assert reopen(client, claim_id).status_code == 409
    assert client.get(f"/api/claims/{claim_id}").json()["status"] == "Pending"


def test_it_can_only_be_handed_off_once(client, today):
    claim_id = create(client).json()["claim"]["claim_id"]
    assert hand_off(client, claim_id).status_code == 200
    assert hand_off(client, claim_id).status_code == 409


def test_reopening_needs_confirmation_and_then_either_route_is_open(client, today):
    claim_id = create(client).json()["claim"]["claim_id"]
    hand_off(client, claim_id)
    assert reopen(client, claim_id, confirmed=False).status_code == 422
    assert client.get(f"/api/claims/{claim_id}").json()["status"] == "Handed off"

    res = reopen(client, claim_id)
    assert res.status_code == 200, res.text
    assert res.json()["claim"]["status"] == "Draft"
    assert res.json()["claim"]["handoff"] is None
    assert submit(client, claim_id).status_code == 200


def test_a_handed_off_claim_cannot_be_changed_until_reopened(client, today):
    claim_id = flagged_draft(client)
    suggestion = next(
        s for s in client.get(f"/api/aifix/{claim_id}").json()["suggestions"] if s["rule_id"] == "RULE-002"
    )
    hand_off(client, claim_id, acknowledge_open_issues=True)
    fix = {"suggestion_id": suggestion["id"], "values": {"pa_number": "AUTH-42"}}
    assert client.post(f"/api/aifix/{claim_id}/apply", json=fix).status_code == 409
    assert client.delete(f"/api/aifix/{claim_id}/corrections").status_code == 409

    reopen(client, claim_id)
    assert client.post(f"/api/aifix/{claim_id}/apply", json=fix).status_code == 200


def test_it_never_ages_or_joins_the_queue_and_stays_out_of_ar(client, today):
    claim_id = flagged_draft(client)
    hand_off(client, claim_id, acknowledge_open_issues=True)
    today(date(2027, 1, 1))
    claim = client.get(f"/api/claims/{claim_id}").json()
    assert (claim["days_in_ar"], claim["is_overdue"]) == (0, False)
    queue = client.get("/api/claims", params={"needs_attention": True, "search": claim_id}).json()
    assert queue["total"] == 0
    found = client.get("/api/claims", params={"status": "Handed off"}).json()["items"]
    assert [c["claim_id"] for c in found] == [claim_id]


def test_it_survives_a_restart_and_so_does_reopening(client, today):
    first = create(client).json()["claim"]["claim_id"]
    second = create(client).json()["claim"]["claim_id"]
    hand_off(client, first)
    hand_off(client, second)
    reopen(client, second)

    store = get_new_claim_store("meridian")
    records = {r["fields"]["claim_id"]: r for r in store.records()}
    assert records[first]["handoff"]["handed_off_by"]
    assert records[second]["handoff"] is None

    reloaded = ClaimsRepository(repository.get_repository("meridian").data_dir, new_claims=store)
    assert reloaded.get_claim(first).status == "Handed off"
    assert reloaded.get_claim(first).handoff is not None
    assert reloaded.get_claim(second).status == "Draft"


def test_each_step_is_in_the_audit_log(client, today):
    claim_id = flagged_draft(client)
    hand_off(client, claim_id, acknowledge_open_issues=True)
    reopen(client, claim_id)
    events = {e.action: e for e in get_audit_log("meridian").search(AuditQuery())}
    assert "RULE-002" in str(events["POST /api/claims/{claim_id}/hand-off"].detail)
    assert events["POST /api/claims/{claim_id}/reopen"].detail["confirmed_not_sent"] is True


def test_an_analyst_can_do_neither(anon_client, today):
    admin = sign_in(anon_client, Role.ADMIN)
    claim_id = create(admin).json()["claim"]["claim_id"]
    analyst = sign_in(anon_client, Role.ANALYST)
    assert hand_off(analyst, claim_id).status_code == 403
    assert reopen(analyst, claim_id).status_code == 403


def test_the_organisation_default_is_validate_only_and_an_admin_can_change_it(client):
    me = client.get("/api/auth/me").json()
    assert me["organisation"]["default_claim_route"] == "validate_only"
    res = client.put("/api/organisation/settings", json={"default_claim_route": "send"})
    assert res.status_code == 200, res.text
    assert client.get("/api/auth/me").json()["organisation"]["default_claim_route"] == "send"


def test_a_biller_cannot_change_the_default(anon_client):
    biller = sign_in(anon_client, Role.BILLER)
    res = biller.put("/api/organisation/settings", json={"default_claim_route": "send"})
    assert res.status_code == 403
