"""Need-to-know access: an administrator can limit a person to facilities, departments,
or providers; everything they see and do stays inside that scope.

Meridian's fixture claims:
    CLM0000001  PAT000001  PROV001  FAC001  DEPT02 (Internal Medicine)  Paid
    CLM0000002  PAT000002  PROV002  FAC001  DEPT05 (Gastroenterology)   Denied
    CLM0000003  PAT000002  PROV001  FAC002  DEPT02                      Paid
    CLM0000004  PAT000001  PROV002  FAC002  DEPT05                      Denied
"""

import re

import pytest

from app.models import Role
from app.tests.conftest import api_routes, sign_in
from app.tests.test_claim_entry import NEW_CLAIM


def limit(client, username="biller1", **scope):
    sign_in(client, Role.ADMIN)
    res = client.patch(f"/api/users/{username}", json={"scope": scope})
    assert res.status_code == 200, res.text
    return res.json()


def visible(client):
    return sorted(c["claim_id"] for c in client.get("/api/claims", params={"page_size": 50}).json()["items"])


@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        ({"departments": ["DEPT02"]}, ["CLM0000001", "CLM0000003"]),
        ({"facilities": ["FAC002"]}, ["CLM0000003", "CLM0000004"]),
        ({"providers": ["PROV002"]}, ["CLM0000002", "CLM0000004"]),
        # Any match counts: Internal Medicine, plus Dr. Two's claims wherever they are
        ({"departments": ["DEPT02"], "providers": ["PROV002"]}, ["CLM0000001", "CLM0000002", "CLM0000003", "CLM0000004"]),
        ({}, ["CLM0000001", "CLM0000002", "CLM0000003", "CLM0000004"]),  # whole organisation
    ],
)
def test_a_limited_person_sees_only_their_part_of_the_organisation(client, scope, expected):
    limit(client, **scope)
    sign_in(client, Role.BILLER)
    assert visible(client) == expected


def test_out_of_scope_claims_are_not_found_on_every_route(client):
    limit(client, departments=["DEPT02"])
    sign_in(client, Role.BILLER)
    checked = 0
    for method, path in api_routes():
        if "{claim_id}" not in path:
            continue
        url = path.replace("{claim_id}", "CLM0000002")
        res = client.request(method, url, json={})
        assert res.status_code in (403, 404, 422), f"{method} {url} -> {res.status_code}"
        assert "Gastroenterology" not in res.text and "DEN0000001" not in res.text
        checked += 1
    assert checked >= 9  # every route with a claim ID (a broken walk would find none)
    # Batch validation treats it as unknown too
    res = client.post("/api/validate", json={"claim_ids": ["CLM0000001", "CLM0000002"]})
    assert res.status_code == 404 and "CLM0000002" in res.text


def test_the_overview_and_queue_count_only_the_scope(client):
    limit(client, departments=["DEPT02"])
    sign_in(client, Role.BILLER)
    kpis = {k["key"]: k for k in client.get("/api/dashboard").json()["kpis"]}
    assert kpis["claims"]["value"] == 2
    assert kpis["denial_rate"]["value"] == 0  # both denials are in Gastroenterology
    assert client.get("/api/claims", params={"needs_attention": True}).json()["total"] == 0
    # An area with no claims gets an empty Overview, not an error
    empty = client.get("/api/dashboard", params={"payer_id": "PAY010"})
    assert empty.status_code == 200 and empty.json()["period"] is None


def test_the_patient_register_is_organisation_wide_but_history_is_scoped(client):
    limit(client, departments=["DEPT02"])
    sign_in(client, Role.BILLER)
    # PAT000002 has CLM0000002 (Gastroenterology, denied) and CLM0000003 (Internal Medicine)
    patient = client.get("/api/patients/PAT000002").json()
    assert (patient["claim_count"], patient["denial_count"]) == (1, 0)
    found = client.get("/api/patients", params={"search": "PAT00000"}).json()["total"]
    sign_in(client, Role.ADMIN)
    assert client.get("/api/patients", params={"search": "PAT00000"}).json()["total"] == found


def test_new_claims_and_pick_lists_stay_inside_the_scope(client, today):
    limit(client, departments=["DEPT05"])
    sign_in(client, Role.BILLER)
    assert [p["provider_id"] for p in client.get("/api/providers").json()] == ["PROV002"]
    assert [d["department_id"] for d in client.get("/api/departments").json()] == ["DEPT05"]
    # NEW_CLAIM is Dr. Test One (Internal Medicine): outside Gastroenterology
    res = client.post("/api/claims", json=NEW_CLAIM)
    assert res.status_code == 403
    assert client.post("/api/claims", json={**NEW_CLAIM, "provider_id": "PROV002"}).status_code == 201


def test_saved_forms_follow_the_scope_and_unassigned_ones_are_shared(client):
    sign_in(client, Role.ADMIN)
    gastro = client.post("/api/drafts", json={"patient_id": "PAT000002", "provider_id": "PROV002"}).json()
    unassigned = client.post("/api/drafts", json={"patient_id": "PAT000001"}).json()
    limit(client, departments=["DEPT02"])
    sign_in(client, Role.BILLER)
    assert [d["id"] for d in client.get("/api/drafts").json()] == [unassigned["id"]]
    assert client.get(f"/api/drafts/{gastro['id']}").status_code == 404
    assert client.delete(f"/api/drafts/{gastro['id']}").status_code == 404
    assert client.post("/api/drafts", json={"provider_id": "PROV002"}).status_code == 403


def test_administrators_set_scope_with_safeguards(client):
    sign_in(client, Role.ADMIN)
    # Unknown or another organisation's IDs are refused
    res = client.patch("/api/users/biller1", json={"scope": {"departments": ["DEPT91"]}})
    assert res.status_code == 422 and "DEPT91" in res.text
    # Administrators always see everything
    res = client.patch("/api/users/admin1", json={"scope": {"departments": ["DEPT02"]}})
    assert res.status_code == 422
    # Limiting applies on the next request; promoting clears the limits
    limit(client, departments=["DEPT02"])
    sign_in(client, Role.BILLER)
    assert client.get("/api/auth/me").json()["access"] == "Internal Medicine"
    assert len(visible(client)) == 2
    sign_in(client, Role.ADMIN)
    promoted = client.patch("/api/users/biller1", json={"role": "admin"}).json()
    assert promoted["scope"] == {"facilities": [], "departments": [], "providers": []}
    # Back to whole-organisation access by clearing the limits
    client.patch("/api/users/biller1", json={"role": "biller"})
    limit(client, departments=["DEPT02"])
    cleared = limit(client, departments=[])
    assert not any(cleared["scope"].values())


def test_scope_changes_are_audited(client):
    from app.data.audit import get_audit_log

    limit(client, providers=["PROV001"])
    (event,) = [e for e in get_audit_log("meridian").events() if e.action == "PATCH /api/users/{username}"]
    assert event.detail == {"scope": {"facilities": [], "departments": [], "providers": ["PROV001"]}}
    assert re.search("biller1", str(event.records))


def test_limited_people_create_and_fix_claims_beside_others_work(client, today):
    # The newest claim and a correction belong to a department the biller can't see
    other = client.post("/api/claims", json={**NEW_CLAIM, "pa_required": True}).json()["claim"]["claim_id"]
    fix = {"suggestion_id": f"{other}:RULE-002", "values": {"pa_number": "A-1"}}
    assert client.post(f"/api/aifix/{other}/apply", json=fix).status_code == 200
    limit(client, departments=["DEPT05"])
    sign_in(client, Role.BILLER)
    # Their claim still gets the next ID across the organisation…
    res = client.post("/api/claims", json={**NEW_CLAIM, "provider_id": "PROV002", "pa_required": True})
    assert res.status_code == 201, res.text
    mine = res.json()["claim"]["claim_id"]
    assert int(mine[3:]) == int(other[3:]) + 1
    # …and AI Fix and undo work on it
    fix = {"suggestion_id": f"{mine}:RULE-002", "values": {"pa_number": "B-2"}}
    assert client.post(f"/api/aifix/{mine}/apply", json=fix).status_code == 200
    assert client.delete(f"/api/aifix/{mine}/corrections").status_code == 200
    # They can't undo the other department's correction
    assert client.delete(f"/api/aifix/{other}/corrections").status_code == 404
    sign_in(client, Role.ADMIN)
    assert client.get(f"/api/claims/{other}").json()["pa_number"] == "A-1"
