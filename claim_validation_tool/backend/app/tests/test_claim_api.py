"""The claims API for hospital systems: API keys, sending a claim, and getting back its
errors and suggested fixes."""

import base64
import json

import pytest

from app.data.api_keys import get_api_keys
from app.data.audit import get_audit_log
from app.data.new_claims import get_new_claim_store
from app.data.repository import get_repository
from app.models import Role
from app.services.auth import get_api_rate_limit
from app.tests.conftest import sign_in
from app.tests.test_claim_entry import NEW_CLAIM
from app.tests.test_claim_import import HEADER
from app.tests.test_edi import submitted_837

URL = "/api/v1/claims"


def new_key(org="meridian", name="Billing system"):
    return get_api_keys().create(org, name, "admin1")


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def headers(anon_client, today):
    return auth(new_key()[1])


def send(client, headers, number="ACCT-1001", **changes):
    return client.post(URL, json={**NEW_CLAIM, "claim_number": number, **changes}, headers=headers)


def events(org="meridian"):
    return get_audit_log(org).events()


# ----- Getting in ------------------------------------------------------------------------


def test_needs_a_valid_key_and_a_session_is_not_enough(anon_client, today):
    assert anon_client.get(f"{URL}/CLM0000001").status_code == 401
    bad = anon_client.get(f"{URL}/CLM0000001", headers=auth("crcm_00000000_nope"))
    assert bad.status_code == 401
    assert bad.headers["www-authenticate"] == "Bearer"
    signed_in = sign_in(anon_client, Role.ADMIN)
    assert signed_in.get(f"{URL}/CLM0000001").status_code == 401


def test_a_key_opens_nothing_outside_the_claims_api(anon_client, headers):
    assert anon_client.get(f"{URL}/CLM0000001", headers=headers).status_code == 200
    for path in ("/api/claims", "/api/patients", "/api/users", "/api/audit", "/api/organisation/api-keys"):
        assert anon_client.get(path, headers=headers).status_code == 401, path


def test_a_right_id_with_the_wrong_secret_is_refused_and_the_org_sees_it(anon_client, today):
    key, token = new_key()
    assert anon_client.get(f"{URL}/CLM0000001", headers=auth(token + "x")).status_code == 401
    event = events()[-1]
    assert event.username == f"api.{key.id}" and event.status_code == 401
    assert token not in json.dumps(event.model_dump(mode="json"))


def test_a_revoked_key_stops_working_straight_away(client, today):
    made = client.post("/api/organisation/api-keys", json={"name": "Old interface"}).json()
    client.cookies.clear()
    headers = auth(made["token"])
    assert client.get(f"{URL}/CLM0000001", headers=headers).status_code == 200
    sign_in(client, Role.ADMIN)
    revoked = client.delete(f"/api/organisation/api-keys/{made['key']['id']}")
    assert revoked.status_code == 200 and revoked.json()["revoked_by"] == "admin1"
    client.cookies.clear()
    assert client.get(f"{URL}/CLM0000001", headers=headers).status_code == 401


def test_a_suspended_organisations_key_gets_nothing(anon_client, headers):
    from app.data.orgs import OrgStatus, get_org_registry

    get_org_registry().set_status("meridian", OrgStatus.SUSPENDED)
    res = anon_client.get(f"{URL}/CLM0000001", headers=headers)
    assert res.status_code == 403
    assert "suspended" in res.json()["detail"]


def test_too_many_requests_are_turned_away_per_key(anon_client, today, monkeypatch):
    monkeypatch.setenv("RCM_API_RATE_PER_MINUTE", "2")
    get_api_rate_limit.cache_clear()
    busy, quiet = auth(new_key(name="Busy")[1]), auth(new_key(name="Quiet")[1])
    for _ in range(2):
        assert anon_client.get(f"{URL}/CLM0000001", headers=busy).status_code == 200
    res = anon_client.get(f"{URL}/CLM0000001", headers=busy)
    assert res.status_code == 429
    assert int(res.headers["retry-after"]) >= 1
    assert anon_client.get(f"{URL}/CLM0000001", headers=quiet).status_code == 200


# ----- Managing keys ---------------------------------------------------------------------


def test_the_key_is_shown_once_and_only_its_digest_is_kept(client, today):
    res = client.post("/api/organisation/api-keys", json={"name": "Epic test"})
    assert res.status_code == 201, res.text
    token = res.json()["token"]
    assert token.startswith("crcm_")
    listed = client.get("/api/organisation/api-keys").json()
    assert [k["name"] for k in listed] == ["Epic test"]
    assert token not in json.dumps(listed) and "digest" not in listed[0]
    stored = get_api_keys().path
    assert token not in stored.read_text()
    assert stored.stat().st_mode & 0o777 == 0o600
    audit = json.dumps(events()[-2].model_dump(mode="json")) + json.dumps(events()[-1].model_dump(mode="json"))
    assert token not in audit


def test_keys_survive_a_restart(client, today):
    token = client.post("/api/organisation/api-keys", json={"name": "Epic test"}).json()["token"]
    get_api_keys.cache_clear()
    client.cookies.clear()
    assert client.get(f"{URL}/CLM0000001", headers=auth(token)).status_code == 200


def test_only_administrators_manage_keys_and_only_their_own(client, today):
    made = client.post("/api/organisation/api-keys", json={"name": "Epic test"}).json()
    sign_in(client, Role.BILLER)
    assert client.get("/api/organisation/api-keys").status_code == 403
    assert client.post("/api/organisation/api-keys", json={"name": "x"}).status_code == 403
    sign_in(client, Role.ADMIN, org="lakeside")
    assert client.get("/api/organisation/api-keys").json() == []
    assert client.delete(f"/api/organisation/api-keys/{made['key']['id']}").status_code == 404
    client.cookies.clear()
    assert client.get(f"{URL}/CLM0000001", headers=auth(made["token"])).status_code == 200


def test_key_names_and_the_limit_are_checked(client, today):
    assert client.post("/api/organisation/api-keys", json={"name": "   "}).status_code == 422
    assert client.post("/api/organisation/api-keys", json={"name": "Epic"}).status_code == 201
    assert client.post("/api/organisation/api-keys", json={"name": "epic"}).status_code == 409
    for n in range(9):
        assert client.post("/api/organisation/api-keys", json={"name": f"System {n}"}).status_code == 201
    assert client.post("/api/organisation/api-keys", json={"name": "One more"}).status_code == 409


def test_deleting_an_organisation_revokes_its_keys(anon_client, headers):
    from app.data.org_lifecycle import delete_organisation
    from app.data.orgs import OrgStatus, get_org_registry

    assert anon_client.get(f"{URL}/CLM0000001", headers=headers).status_code == 200
    get_org_registry().set_status("meridian", OrgStatus.SUSPENDED)
    assert any("API key" in line for line in delete_organisation("meridian"))
    assert anon_client.get(f"{URL}/CLM0000001", headers=headers).status_code == 401


# ----- Sending claims --------------------------------------------------------------------


def test_a_claim_comes_back_with_its_findings_and_no_patient_details(anon_client, headers):
    res = send(anon_client, headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["action"], body["status"], body["claim_number"]) == ("created", "Draft", "ACCT-1001")
    assert body["claim_id"] == "CLM0000005"
    assert isinstance(body["findings"], list) and isinstance(body["suggestions"], list)
    assert body["clean"] is (not body["open_issues"])
    text = res.text
    for private in ("Davis", "1976-05-02", "12 Oak St", "MBR123456"):
        assert private not in text


def test_errors_come_back_with_a_suggested_fix_and_clear_when_corrected(anon_client, headers):
    res = send(anon_client, headers, pa_required=True).json()
    assert res["clean"] is False
    assert [f["rule_id"] for f in res["findings"]] == ["RULE-002"]
    assert res["open_issues"][0].startswith("RULE-002")
    fix = next(s for s in res["suggestions"] if s["rule_id"] == "RULE-002")
    assert fix["summary"] and fix["steps"]
    # The hospital corrects it in its own system and sends it again
    fixed = send(anon_client, headers, pa_required=True, pa_obtained=True, pa_number="PA-77").json()
    assert (fixed["action"], fixed["claim_id"]) == ("replaced", res["claim_id"])
    assert (fixed["clean"], fixed["findings"], fixed["suggestions"]) == (True, [], [])


def test_a_submitted_claims_findings_arent_reported_as_clean(anon_client, headers):
    body = anon_client.get(f"{URL}/CLM0000002", headers=headers).json()
    assert body["status"] == "Denied" and body["action"] == "none"
    serious = [f for f in body["findings"] if f["severity"] in ("error", "warning")]
    assert serious
    assert body["clean"] is False
    assert len(body["open_issues"]) == len(serious)


def test_sending_the_number_again_replaces_the_draft(anon_client, headers):
    first = send(anon_client, headers).json()
    again = send(
        anon_client,
        headers,
        lines=[{"cpt_code": "99214", "icd10_pointer": "E11.65"}],
    )
    assert again.status_code == 200, again.text
    assert (again.json()["action"], again.json()["claim_id"]) == ("replaced", first["claim_id"])
    claim = get_repository("meridian").get_claim(first["claim_id"])
    assert [line.cpt_code for line in claim.lines] == ["99214"]
    numbers = [ref for ref in get_repository("meridian")._source_refs.values() if ref == "ACCT-1001"]
    assert len(numbers) == 1


def test_a_retry_of_the_same_claim_makes_no_second_claim(anon_client, headers):
    ids = {send(anon_client, headers).json()["claim_id"] for _ in range(3)}
    assert len(ids) == 1


def test_a_replaced_claims_number_and_changes_survive_a_restart(anon_client, headers):
    claim_id = send(anon_client, headers).json()["claim_id"]
    send(anon_client, headers, lines=[{"cpt_code": "99214", "icd10_pointer": "E11.65"}])
    get_repository.cache_clear()
    get_new_claim_store.cache_clear()
    res = send(anon_client, headers, lines=[{"cpt_code": "99213", "icd10_pointer": "E11.65"}])
    assert (res.json()["action"], res.json()["claim_id"]) == ("replaced", claim_id)


def test_a_different_patient_under_the_same_number_is_refused(anon_client, headers):
    send(anon_client, headers)
    res = send(anon_client, headers, patient_id="PAT000001")
    assert res.status_code == 409
    assert "patient" in res.json()["detail"]


def test_a_finished_claim_cant_be_replaced(anon_client, headers):
    claim_id = send(anon_client, headers).json()["claim_id"]
    done = anon_client.post(f"{URL}/{claim_id}/handoff", json={"acknowledge_open_issues": True}, headers=headers)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "Handed off"
    res = send(anon_client, headers)
    assert res.status_code == 409
    assert claim_id in res.json()["detail"]
    assert anon_client.get(f"{URL}/{claim_id}", headers=headers).json()["status"] == "Handed off"


def test_handing_off_with_open_issues_needs_acknowledging(anon_client, headers, monkeypatch):
    from app.routers import claim_api, claims

    claim_id = send(anon_client, headers).json()["claim_id"]
    monkeypatch.setattr(claims, "_open_issues", lambda *a: ["RULE-001 Something"])
    monkeypatch.setattr(claim_api, "_open_issues", lambda *a: ["RULE-001 Something"])
    res = anon_client.post(f"{URL}/{claim_id}/handoff", headers=headers)
    assert res.status_code == 422
    done = anon_client.post(f"{URL}/{claim_id}/handoff", json={"acknowledge_open_issues": True}, headers=headers)
    assert done.status_code == 200
    assert done.json()["open_issues"] == ["RULE-001 Something"]
    assert done.json()["clean"] is False
    claim = get_repository("meridian").get_claim(claim_id)
    assert claim.handoff.handed_off_by.startswith("api.")


def test_a_bad_claim_says_why_and_saves_nothing(anon_client, headers):
    before = len(get_repository("meridian").claims_frame())
    assert send(anon_client, headers, number="").status_code == 422
    assert send(anon_client, headers, patient_id="PAT999999").status_code in (404, 422)
    assert send(anon_client, headers, service_date="not-a-date").status_code == 422
    assert len(get_repository("meridian").claims_frame()) == before


def test_organisations_cant_reach_each_other(anon_client, headers):
    claim_id = send(anon_client, headers).json()["claim_id"]
    other = auth(new_key(org="lakeside")[1])
    assert anon_client.get(f"{URL}/{claim_id}", headers=other).status_code == 404
    assert anon_client.post(f"{URL}/{claim_id}/handoff", headers=other).status_code == 404
    # The same number means a different claim there
    assert get_repository("lakeside").claim_id_for_number("ACCT-1001") is None


def test_a_sent_claim_shows_up_for_staff(anon_client, headers):
    claim_id = send(anon_client, headers).json()["claim_id"]
    client = sign_in(anon_client, Role.BILLER)
    claim = client.get(f"/api/claims/{claim_id}").json()
    assert (claim["status"], claim["source_ref"]) == ("Draft", "ACCT-1001")


def test_sending_is_audited_without_the_claim_number_or_patient_details(anon_client, headers):
    claim_id = send(anon_client, headers).json()["claim_id"]
    event = events()[-1]
    assert event.action == "POST /api/v1/claims"
    assert event.username.startswith("api.") and event.role == "biller"
    assert event.records["claim_id"] == claim_id
    assert event.detail["action_taken"] == "created"
    text = json.dumps(event.model_dump(mode="json"))
    for private in ("ACCT-1001", "Davis", "MBR123456"):
        assert private not in text


# ----- Files -----------------------------------------------------------------------------


def send_file(client, headers, content: str, filename="claims.csv"):
    payload = {"filename": filename, "content": base64.b64encode(content.encode()).decode()}
    return client.post(f"{URL}/file", json=payload, headers=headers)


def rows(*lines):
    return "\n".join([HEADER, *lines]) + "\n"


GOOD = "A1,PAT000003,PAY001,PROV001,2026-01-05,E11.65,99213,E11.65,1,MBR123456"


def test_a_file_checks_each_claim_and_reports_the_ones_it_cant(anon_client, headers):
    bad = "A2,PAT999999,PAY001,PROV001,2026-01-05,E11.65,99213,E11.65,1,MBR123456"
    res = send_file(anon_client, headers, rows(GOOD, bad))
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["file_type"], body["claims_found"]) == ("csv", 2)
    assert [(c["claim_number"], c["action"]) for c in body["checked"]] == [("A1", "created")]
    assert [f["ref"] for f in body["failed"]] == ["A2"]
    assert "Davis" not in res.text


def test_sending_a_file_again_replaces_its_drafts(anon_client, headers):
    first = send_file(anon_client, headers, rows(GOOD)).json()["checked"][0]
    again = send_file(anon_client, headers, rows(GOOD)).json()["checked"][0]
    assert (again["action"], again["claim_id"]) == ("replaced", first["claim_id"])


def test_a_finished_claim_in_a_file_fails_alone(anon_client, headers):
    first = send_file(anon_client, headers, rows(GOOD)).json()["checked"][0]
    anon_client.post(f"{URL}/{first['claim_id']}/handoff", json={"acknowledge_open_issues": True}, headers=headers)
    other = "A3,PAT000003,PAY001,PROV001,2026-01-05,E11.65,99213,E11.65,1,MBR123456"
    body = send_file(anon_client, headers, rows(GOOD, other)).json()
    assert [c["claim_number"] for c in body["checked"]] == ["A3"]
    assert [f["ref"] for f in body["failed"]] == ["A1"]


def test_a_number_twice_in_one_837_fails_rather_than_overwriting(anon_client, headers, monkeypatch):
    from app.services.claim_import import ParsedClaim
    from app.routers import claim_api
    from app.models import ClaimCreate

    body = ClaimCreate.model_validate(NEW_CLAIM)
    parsed = [ParsedClaim(ref="DUP", where=f"claim {n}", body=body) for n in (1, 2)]
    monkeypatch.setattr(claim_api, "read_claims_file", lambda *a: ("837P", parsed))
    res = send_file(anon_client, headers, "ignored").json()
    assert res["checked"] == []
    assert all("more than once" in f["errors"][0] for f in res["failed"])


def test_an_837_from_a_billing_system_goes_through(client, today):
    text = submitted_837(client)[1].text
    client.cookies.clear()
    headers = auth(new_key()[1])
    res = send_file(client, headers, text, filename="claims.837")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["file_type"] in ("837P", "837I")
    assert len(body["checked"]) + len(body["failed"]) == body["claims_found"] >= 1
