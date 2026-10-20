"""Editing a Draft claim entered in the app (PUT /api/claims/{id})."""

from app.data import repository
from app.data.audit import get_audit_log
from app.data.corrections import get_correction_store
from app.data.new_claims import get_new_claim_store
from app.models import Role
from app.tests.conftest import sign_in
from app.tests.test_claim_entry import NEW_CLAIM, create, submit


def edit(client, claim_id, **changes):
    return client.put(f"/api/claims/{claim_id}", json={**NEW_CLAIM, **changes})


def test_a_forgotten_prior_authorisation_is_added_by_editing(client, today):
    claim_id = create(client).json()["claim"]["claim_id"]
    res = edit(client, claim_id, pa_required=True, pa_obtained=True, pa_number="PA-2026-118")
    assert res.status_code == 200, res.text
    claim = res.json()["claim"]
    assert claim["claim_id"] == claim_id and claim["status"] == "Draft"
    assert (claim["pa_required"], claim["pa_obtained"], claim["pa_number"]) == (True, True, "PA-2026-118")
    assert res.json()["validation"]["status"] == "pass"
    # Same claim, not a new one
    assert client.get("/api/claims", params={"search": claim_id}).json()["total"] == 1


def test_edits_re_run_the_rules(client, today):
    claim_id = create(client).json()["claim"]["claim_id"]
    # Required but not obtained trips Missing Prior Authorization, which blocks submission
    res = edit(client, claim_id, pa_required=True)
    assert "RULE-002" in {f["rule_id"] for f in res.json()["validation"]["findings"]}
    assert submit(client, claim_id).status_code == 422


def test_lines_codes_and_billing_are_replaced(client):
    claim_id = create(client).json()["claim"]["claim_id"]
    lines = [
        {"cpt_code": "99213", "icd10_pointer": "E11.65", "units": 1},
        {"cpt_code": "99214", "icd10_pointer": "E11.65", "units": 2},
    ]
    billing = {**NEW_CLAIM["billing"], "patient_address": {**NEW_CLAIM["billing"]["patient_address"], "line1": "40 Elm Ave"}}
    claim = edit(client, claim_id, lines=lines, billing=billing).json()["claim"]
    assert [(line["line_number"], line["cpt_code"]) for line in claim["lines"]] == [(1, "99213"), (2, "99214")]
    assert claim["billing"]["patient_address"]["line1"] == "40 Elm Ave"
    assert client.get(f"/api/claims/{claim_id}").json()["lines"] == claim["lines"]


def test_edits_survive_a_restart(client):
    claim_id = create(client).json()["claim"]["claim_id"]
    edit(client, claim_id, pa_required=True, pa_obtained=True, pa_number="PA-9")
    records = [r for r in get_new_claim_store("meridian").records() if r["fields"]["claim_id"] == claim_id]
    assert len(records) == 1 and records[0]["fields"]["pa_number"] == "PA-9"
    repository.get_repository.cache_clear()
    assert client.get(f"/api/claims/{claim_id}").json()["pa_number"] == "PA-9"


def test_only_unsubmitted_claims_entered_here_can_be_edited(client, today):
    claim_id = create(client).json()["claim"]["claim_id"]
    submit(client, claim_id)
    assert edit(client, claim_id).status_code == 409  # submitted: locked
    assert edit(client, "CLM0000001").status_code == 409  # source data
    assert edit(client, "CLM9999999").status_code == 404
    other = create(client).json()["claim"]["claim_id"]
    assert edit(client, other, patient_id="PAT000001").status_code == 409  # patient is fixed


def test_editing_needs_permission_and_access(client):
    claim_id = create(client).json()["claim"]["claim_id"]
    sign_in(client, Role.ANALYST)
    assert edit(client, claim_id).status_code == 403
    sign_in(client, Role.ADMIN, "lakeside")
    assert edit(client, claim_id).status_code == 404  # another organisation's claim


def test_ai_fix_corrections_are_folded_in(client, today):
    claim_id = create(client, pa_required=True).json()["claim"]["claim_id"]
    client.post(
        f"/api/aifix/{claim_id}/apply",
        json={"suggestion_id": f"{claim_id}:RULE-002", "values": {"pa_number": "AUTH-9"}},
    )
    # The form starts from the corrected values and is saved as the claim
    claim = edit(client, claim_id, pa_required=True, pa_obtained=True, pa_number="AUTH-9").json()["claim"]
    assert claim["pa_number"] == "AUTH-9" and claim["has_corrections"] is False
    assert get_correction_store("meridian").for_claim(claim_id) == []


def test_the_audit_log_names_what_changed_not_the_values(client):
    claim_id = create(client).json()["claim"]["claim_id"]
    edit(client, claim_id, pa_required=True, pa_obtained=True, pa_number="PA-SECRET")
    (event,) = [e for e in get_audit_log("meridian").events() if e.action == "PUT /api/claims/{claim_id}"]
    assert event.records == {"claim_id": claim_id}
    assert event.detail["changed"] == ["pa_required", "pa_obtained", "pa_number"]
    assert "PA-SECRET" not in event.model_dump_json()
