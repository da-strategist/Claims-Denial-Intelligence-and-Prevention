"""Manual claim entry: POST /api/claims, and the Draft -> Pending lifecycle."""

from datetime import date

import pytest

from app.data import repository
from app.data.corrections import CorrectionStore, get_correction_store
from app.tests.conftest import FIXTURES_DIR

# PAT000003 (Donald Davis) is registered with PAY001 as primary payer and has no claims;
# PROV001 is in DEPT02; CPT 99213 has a $95 standard charge
NEW_CLAIM = {
    "patient_id": "PAT000003",
    "payer_id": "PAY001",
    "provider_id": "PROV001",
    "diagnoses": ["E11.65"],
    "lines": [{"cpt_code": "99213", "icd10_pointer": "E11.65"}],
    "claim_type": "Professional",
    "service_date": "2026-01-05",
    "submission_date": "2026-01-06",
    "billing": {
        "patient_birth_date": "1976-05-02",
        "patient_address": {"line1": "12 Oak St", "city": "Charlotte", "state": "NC", "zip_code": "28205"},
        "policy": {"member_id": "MBR123456"},
    },
}


def create(client, **changes):
    body = {**NEW_CLAIM, **changes}
    # Each other payer needs its policy; give one unless the test sets billing itself
    others = body.get("other_payer_ids", [])
    if others and "billing" not in changes:
        policies = [{"member_id": f"OTHER{n}"} for n in range(len(others))]
        body["billing"] = {**NEW_CLAIM["billing"], "other_policies": policies}
    return client.post("/api/claims", json=body)


def test_create_claim_assigns_ids_and_defaults(client):
    res = create(client)
    assert res.status_code == 201, res.text
    claim = res.json()["claim"]
    assert claim["claim_id"] == "CLM0000005"  # fixtures end at CLM0000004
    assert claim["patient"]["last_name"] == "Davis"
    assert (claim["provider_id"], claim["department_id"]) == ("PROV001", "DEPT02")
    assert claim["facility_id"] == "FAC001"
    assert claim["place_of_service"] == "11"
    assert (claim["primary_icd10"], claim["additional_icd10"]) == ("E11.65", [])
    assert claim["total_charge"] == 95.0  # standard charge × 1 unit
    assert (claim["status"], claim["total_paid"], claim["days_in_ar"]) == ("Draft", 0, 0)
    assert claim["is_overdue"] is False
    assert claim["is_clean_claim"] is True  # nothing known to be wrong yet
    assert [(line["cpt_code"], line["cpt_category"], line["charge_amount"]) for line in claim["lines"]] == [
        ("99213", "E&M", 95.0)
    ]
    assert claim["denials"] == []
    assert claim["payer"]["payer_name"] == "Medicare FFS"


def test_new_claim_is_validated_and_listed(client, today):
    body = create(client, pa_required=True).json()
    validation = body["validation"]
    # Missing prior auth (error); a new claim isn't flagged non-clean
    assert [f["rule_id"] for f in validation["findings"]] == ["RULE-002"]
    assert validation["status"] == "error"

    claim_id = body["claim"]["claim_id"]
    assert client.get(f"/api/claims/{claim_id}").status_code == 200
    listed = client.get("/api/claims", params={"search": claim_id}).json()
    assert [c["claim_id"] for c in listed["items"]] == [claim_id]
    assert client.get(f"/api/validate/{claim_id}").json()["status"] == "error"


def test_ids_keep_incrementing(client):
    first = create(client).json()["claim"]
    second = create(client).json()["claim"]
    assert (first["claim_id"], second["claim_id"]) == ("CLM0000005", "CLM0000006")
    assert first["lines"][0]["line_id"] != second["lines"][0]["line_id"]
    # Both belong to the same registered patient, whose history now shows them
    assert {first["patient_id"], second["patient_id"]} == {"PAT000003"}
    assert client.get("/api/patients/PAT000003").json()["claim_count"] == 2


def test_new_claim_counts_on_dashboard(client):
    before = client.get("/api/dashboard").json()
    create(client, pa_required=True)
    after = client.get("/api/dashboard").json()
    now = {k["key"]: k for k in after["kpis"]}
    assert now["claims"]["value"] == {k["key"]: k["value"] for k in before["kpis"]}["claims"] + 1
    assert now["claims"]["detail"] == "$4.3K billed · 1 draft"
    # Needs attention is submitted claims (CLM0000002); the new draft is listed apart
    assert now["at_risk"]["value"] == 1
    assert after["drafts"] == {"claims": 1, "with_problems": 1}
    # A draft isn't adjudicated or in AR: rates and aging are unchanged
    assert now["denial_rate"]["value"] == 0.5
    assert now["avg_days_in_ar"]["value"] == 33.75
    assert sum(b["claims"] for b in after["ar_aging"]) == 4


def test_ai_fix_works_on_new_claim(client, today):
    claim_id = create(client, pa_required=True).json()["claim"]["claim_id"]
    res = client.post(
        f"/api/aifix/{claim_id}/apply",
        json={"suggestion_id": f"{claim_id}:RULE-002", "values": {"pa_number": "AUTH-9"}},
    )
    assert res.status_code == 200, res.text
    assert res.json()["after"]["validation"]["status"] == "pass"


def test_pa_number_is_stored(client):
    claim = create(client, pa_required=True, pa_obtained=True, pa_number="PA-77").json()["claim"]
    assert (claim["pa_obtained"], claim["pa_number"]) == (True, "PA-77")


def test_multiple_diagnoses_lines_and_payers(client):
    res = create(
        client,
        payer_id="PAY002",
        other_payer_ids=["PAY001"],
        diagnoses=["K21.0", "E11.65"],
        lines=[
            {"cpt_code": "43239", "modifier": "59", "icd10_pointer": "K21.0"},
            {"cpt_code": "99214", "units": 2, "charge_amount": 280, "icd10_pointer": "E11.65"},
        ],
    )
    assert res.status_code == 201, res.text
    claim = res.json()["claim"]
    assert (claim["primary_icd10"], claim["additional_icd10"]) == ("K21.0", ["E11.65"])
    assert (claim["payer_id"], claim["other_payer_ids"]) == ("PAY002", ["PAY001"])
    assert [
        (line["line_number"], line["modifier"], line["units"], line["charge_amount"])
        for line in claim["lines"]
    ] == [(1, "59", 1, 1800.0), (2, None, 2, 280.0)]
    assert claim["total_charge"] == 2080.0
    # Survives a round trip through the claims list
    listed = client.get("/api/claims", params={"search": claim["claim_id"]}).json()["items"][0]
    assert listed["other_payer_ids"] == ["PAY001"]


def test_claim_missing_patients_primary_payer_is_flagged_for_rules(client):
    client.post(
        "/api/rules",
        json={
            "name": "Registered primary payer missing from claim",
            "category": "Eligibility",
            "severity": "warning",
            "conditions": [
                {"field": "patient_primary_on_claim", "operator": "equals", "value": "false"}
            ],
        },
    )

    def flagged(**changes):
        findings = create(client, **changes).json()["validation"]["findings"]
        return "RULE-010" in [f["rule_id"] for f in findings]

    # PAT000003 is registered with PAY001
    assert flagged(payer_id="PAY002")
    assert not flagged()
    # Secondary billing: the primary is listed as other coverage
    assert not flagged(payer_id="PAY002", other_payer_ids=["PAY001"])


def test_patient_denial_history_feeds_risk(client):
    # PAT000002 had DEN0000001 (preventable) on 2025-03-10
    factors = create(client, patient_id="PAT000002", payer_id="PAY002").json()["validation"][
        "risk_factors"
    ]
    labels = [f["label"] for f in factors]
    assert "Patient has prior denials" in labels
    assert "Prior denial was preventable" in labels


@pytest.mark.parametrize(
    ("changes", "detail"),
    [
        ({"submission_date": "2026-01-04"}, None),  # before service date
        ({"diagnoses": ["diabetes"]}, None),
        ({"diagnoses": []}, None),
        ({"lines": []}, None),
        ({"claim_type": "Dental"}, None),
        ({"place_of_service": "99"}, None),
        ({"pa_obtained": True}, None),  # without pa_required
        ({"pa_required": True, "pa_number": "PA-1"}, None),  # number without pa_obtained
        ({"diagnoses": ["E11.65", "I10"]}, "Every diagnosis needs a service line: add one for I10"),
        (
            {"lines": [{"cpt_code": "99213", "icd10_pointer": "I10"}]},
            "Line 1 points at I10, which isn't a listed diagnosis",
        ),
        ({"diagnoses": ["E11.65", "E11.65"]}, "Each diagnosis can only be listed once"),
        ({"other_payer_ids": ["PAY001"]}, "Each payer can only be listed once"),
        ({"other_payer_ids": ["PAY002", "PAY003", "PAY004"]}, None),  # max 2
        ({"lines": [{"cpt_code": "99213", "modifier": "5", "icd10_pointer": "E11.65"}]}, None),
        ({"lines": [{"cpt_code": "99213", "units": 0, "icd10_pointer": "E11.65"}]}, None),
        ({"patient_id": "PAT999999"}, "Patient PAT999999 is not a registered patient"),
        ({"payer_id": "PAY999"}, "Unknown payer PAY999"),
        ({"other_payer_ids": ["PAY999"]}, "Unknown payer PAY999"),
        ({"provider_id": "PROV999"}, "Provider PROV999 is not an active provider"),
        ({"facility_id": "FAC999"}, "Unknown facility FAC999"),
        (
            {"lines": [{"cpt_code": "00000", "icd10_pointer": "E11.65"}]},
            "Line 1: unknown CPT code 00000",
        ),
    ],
)
def test_invalid_claims_are_rejected(client, changes, detail):
    res = create(client, **changes)
    assert res.status_code == 422
    if detail:
        body = res.json()["detail"]
        message = body if isinstance(body, str) else " ".join(e["msg"] for e in body)
        assert detail in message
    assert client.get("/api/claims").json()["total"] == 4


# --- Draft -> Pending -------------------------------------------------------------


def submit(client, claim_id):
    return client.post(f"/api/claims/{claim_id}/submit")


def test_submit_turns_a_clean_draft_pending(client, today):
    claim_id = create(client).json()["claim"]["claim_id"]  # passes every rule
    res = submit(client, claim_id)
    assert res.status_code == 200, res.text
    claim = res.json()["claim"]
    assert (claim["status"], claim["submission_date"], claim["days_in_ar"]) == (
        "Pending",
        "2026-01-10",
        0,
    )
    assert client.get("/api/claims", params={"status": "Pending"}).json()["total"] == 1


def test_submit_refused_while_rule_errors_remain(client, today):
    claim_id = create(client, pa_required=True).json()["claim"]["claim_id"]
    res = submit(client, claim_id)
    assert res.status_code == 422
    assert res.json()["detail"] == (
        "Resolve every rule error and warning before submitting: RULE-002 Missing Prior Authorization"
    )
    # Fixing the error unblocks it
    client.post(
        f"/api/aifix/{claim_id}/apply",
        json={"suggestion_id": f"{claim_id}:RULE-002", "values": {"pa_number": "A-1"}},
    )
    assert submit(client, claim_id).status_code == 200


def test_only_drafts_can_be_submitted(client, today):
    claim_id = create(client).json()["claim"]["claim_id"]
    submit(client, claim_id)
    assert submit(client, claim_id).status_code == 409  # already pending
    assert submit(client, "CLM0000001").status_code == 409  # adjudicated source claim
    assert submit(client, "CLM9999999").status_code == 404


def test_future_service_date_cannot_be_submitted(client, today):
    claim_id = create(client, service_date="2026-02-01", submission_date="2026-02-02").json()[
        "claim"
    ]["claim_id"]
    res = submit(client, claim_id)
    assert res.status_code == 409
    assert "before its service date" in res.json()["detail"]


def test_pending_claims_age_and_go_overdue(client, today):
    # PAY001 (Medicare FFS) averages 32 days to pay in the fixtures
    claim_id = create(client).json()["claim"]["claim_id"]
    submit(client, claim_id)

    today(date(2026, 2, 11))  # 32 days: not yet overdue
    claim = client.get(f"/api/claims/{claim_id}").json()
    assert (claim["days_in_ar"], claim["is_overdue"]) == (32, False)

    today(date(2026, 2, 12))  # 33 days
    claim = client.get(f"/api/claims/{claim_id}").json()
    assert (claim["days_in_ar"], claim["is_overdue"]) == (33, True)
    overdue = client.get("/api/claims", params={"overdue": True}).json()
    assert [c["claim_id"] for c in overdue["items"]] == [claim_id]

    kpis = {k["key"]: k for k in client.get("/api/dashboard").json()["kpis"]}
    assert kpis["avg_days_in_ar"]["detail"] == "0 claims over 60 days · 1 pending overdue"
    assert kpis["denial_rate"]["value"] == 0.5  # pending isn't adjudicated


def test_rules_can_flag_overdue_claims(client, today):
    client.post(
        "/api/rules",
        json={
            "name": "Chase overdue claims",
            "category": "Billing",
            "severity": "warning",
            "conditions": [{"field": "is_overdue", "operator": "equals", "value": "true"}],
        },
    )
    claim_id = create(client).json()["claim"]["claim_id"]
    submit(client, claim_id)
    today(date(2026, 3, 1))
    findings = client.get(f"/api/validate/{claim_id}").json()["findings"]
    assert "RULE-010" in [f["rule_id"] for f in findings]


def test_startup_drops_corrections_for_claims_that_no_longer_exist(tmp_path, monkeypatch):
    # A manual claim was corrected, then the server restarted and the claim is gone
    path = tmp_path / "corrections.json"
    store = CorrectionStore(path)
    store.add("CLM0000005", "CLM0000005:RULE-002", {"pa_number": (None, "OLD-AUTH")})
    store.add("CLM0000002", "CLM0000002:RULE-008", {"is_clean_claim": ("false", "true")})
    monkeypatch.setenv("RCM_DATA_DIR", str(FIXTURES_DIR))
    monkeypatch.setenv("RCM_CORRECTIONS_FILE", str(path))
    monkeypatch.setenv("RCM_NEW_CLAIMS_FILE", str(tmp_path / "new_claims.json"))
    from app.data.new_claims import get_new_claim_store

    get_new_claim_store.cache_clear()
    for cache in (repository.get_repository, get_correction_store):
        cache.cache_clear()
    try:
        repo = repository.get_repository()
        assert CorrectionStore(path).overrides() == {"CLM0000002": {"is_clean_claim": "true"}}
        assert repo.get_claim("CLM0000002").has_corrections is True
    finally:
        for cache in (repository.get_repository, get_correction_store, get_new_claim_store):
            cache.cache_clear()


def test_submit_refused_while_any_warning_remains(client, today):
    # Over $30,000 trips the High Billed Amount Threshold warning (RULE-004)
    line = {**NEW_CLAIM["lines"][0], "charge_amount": 35000}
    claim_id = create(client, lines=[line]).json()["claim"]["claim_id"]
    res = submit(client, claim_id)
    assert res.status_code == 422
    assert res.json()["detail"] == (
        "Resolve every rule error and warning before submitting: RULE-004 High Billed Amount Threshold"
    )
    assert client.get(f"/api/claims/{claim_id}").json()["status"] == "Draft"

    # The rules run again at submission: once the warning's rule is off, it goes through
    client.patch("/api/rules/RULE-004", json={"enabled": False})
    assert submit(client, claim_id).status_code == 200


def test_claims_entered_through_the_api_start_as_drafts(client, today):
    # Submission is the only way out of Draft, so the rules always get the final say
    res = create(client, status="Pending", pa_required=True)
    assert res.status_code == 201
    claim_id = res.json()["claim"]["claim_id"]
    assert res.json()["claim"]["status"] == "Draft"
    assert submit(client, claim_id).status_code == 422


def test_drafts_can_be_left_out_of_the_claim_list(client, today):
    claim_id = create(client).json()["claim"]["claim_id"]
    everything = client.get("/api/claims").json()
    submitted_only = client.get("/api/claims", params={"include_drafts": False}).json()
    assert claim_id in [c["claim_id"] for c in everything["items"]]
    assert submitted_only["total"] == everything["total"] - 1
    assert claim_id not in [c["claim_id"] for c in submitted_only["items"]]


# --- The final check judges the date the claim actually goes out ------------------


def rule_ids(client, claim_id):
    validation = client.get(f"/api/aifix/{claim_id}").json()["validation"]
    return [f["rule_id"] for f in validation["findings"]]


def test_a_draft_left_past_its_planned_date_is_checked_as_of_today(client, today):
    # Service 5 Jan, planned for 6 Jan: on time, so nothing is flagged
    claim_id = create(client).json()["claim"]["claim_id"]
    assert rule_ids(client, claim_id) == []

    # Left as a draft until 20 Feb: 46 days after service, past Timely Filing's 30
    today(date(2026, 2, 20))
    assert rule_ids(client, claim_id) == ["RULE-006"]  # shown before anyone tries to submit
    res = submit(client, claim_id)
    assert res.status_code == 422
    assert "RULE-006 Timely Filing Risk" in res.json()["detail"]


def test_a_late_planned_date_doesnt_block_a_claim_sent_on_time(client, today):
    # Planned 55 days after service, so it's flagged for now...
    claim_id = create(client, submission_date="2026-03-01").json()["claim"]["claim_id"]
    assert rule_ids(client, claim_id) == ["RULE-006"]
    # ...but it goes out today, 5 days after service, which is on time
    res = submit(client, claim_id)
    assert res.status_code == 200, res.text
    assert res.json()["claim"]["submission_date"] == "2026-01-10"


# --- New claims survive restarts ---------------------------------------------------


def restart(client):
    """Drop the in-memory repository and stores, as a server restart would."""
    from app.data.new_claims import get_new_claim_store

    for cache in (repository.get_repository, get_new_claim_store, get_correction_store):
        cache.cache_clear()


def test_new_claims_survive_a_restart(client, today):
    draft_id = create(client, pa_required=True).json()["claim"]["claim_id"]
    client.post(
        f"/api/aifix/{draft_id}/apply",
        json={"suggestion_id": f"{draft_id}:RULE-002", "values": {"pa_number": "AUTH-9"}},
    )
    sent_id = create(client).json()["claim"]["claim_id"]
    today(date(2026, 1, 12))
    assert submit(client, sent_id).status_code == 200

    restart(client)
    today(date(2026, 1, 20))
    draft = client.get(f"/api/claims/{draft_id}").json()
    sent = client.get(f"/api/claims/{sent_id}").json()
    assert (draft["status"], draft["pa_number"], draft["has_corrections"]) == ("Draft", "AUTH-9", True)
    assert (sent["status"], sent["submission_date"], sent["days_in_ar"]) == ("Pending", "2026-01-12", 8)
    # IDs carry on from the saved claims
    assert create(client).json()["claim"]["claim_id"] == "CLM0000007"
