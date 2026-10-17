"""AI Fix tests against the fixture claims (see test_validation_engine.py for the table).

Under the seed rules, CLM0000002 (PAY002, denied) breaks Missing Prior Authorization
(error) and Non-Clean Claim Review (warning), and has a prior-auth denial
(CARC 197 / RARC N362). Its risk score of 55 is below the AI Fix threshold, so its status
is error; suggestions are offered for every finding regardless.
"""

import pytest

from app.data.corrections import CorrectionStore
from app.data.reference import ReferenceData
from app.models import ClaimDetail, ClaimValidation, Rule
from app.services.aifix import ClaimContext, RuleBasedSuggester

CLAIM = "CLM0000002"


def fixes(client, claim_id=CLAIM):
    return client.get(f"/api/aifix/{claim_id}").json()


def by_id(body):
    return {s["id"].split(":", 1)[1]: s for s in body["suggestions"]}


def apply(client, suggestion_id, values=None, claim_id=CLAIM):
    return client.post(
        f"/api/aifix/{claim_id}/apply",
        json={"suggestion_id": f"{claim_id}:{suggestion_id}", "values": values or {}},
    )


def test_suggestions_follow_findings_then_appeal(client):
    body = fixes(client)
    assert body["validation"]["status"] == "error"
    assert list(by_id(body)) == ["RULE-002", "RULE-008", "appeal:DEN0000001"]
    assert body["corrections"] == []


def test_missing_prior_auth_needs_the_auth_number(client):
    suggestion = by_id(fixes(client))["RULE-002"]
    assert suggestion["action"] == "apply"
    assert suggestion["clarification_topic"] == "payer_prior_auth"
    assert suggestion["needs_clarification"] is True
    changes = {c["field"]: c for c in suggestion["changes"]}
    assert changes["pa_obtained"]["suggested_value"] == "true"
    assert changes["pa_obtained"]["current_value"] == "false"
    assert changes["pa_number"]["requires_input"] is True
    sources = {(c["source_type"], c["reference_id"]) for c in suggestion["citations"]}
    assert sources == {("payer", "PAY002"), ("rule", "RULE-002")}


def test_appeal_cites_adjustment_codes(client):
    appeal = by_id(fixes(client))["appeal:DEN0000001"]
    assert appeal["action"] == "clarify"
    assert appeal["clarification_topic"] == "appeal"
    excerpts = {c["reference_id"]: c["excerpt"] for c in appeal["citations"]}
    assert excerpts["197"] == "Precertification/authorization absent (group CO)"
    assert excerpts["N362"] == "Alert: Missing/Incomplete authorization number"


def test_clean_claim_has_no_suggestions(client):
    body = fixes(client, "CLM0000001")
    assert body["validation"]["status"] == "pass"
    assert body["suggestions"] == []


def test_apply_requires_specialist_input(client):
    res = apply(client, "RULE-002")
    assert res.status_code == 422
    assert res.json()["detail"] == "Prior Auth Number is required"
    assert fixes(client)["corrections"] == []


def test_apply_fix_revalidates_and_overlays_the_claim(client):
    res = apply(client, "RULE-002", {"pa_number": "  AUTH-7781 "})
    assert res.status_code == 200
    result = res.json()
    assert result["before"]["status"] == "error"
    assert [f["rule_id"] for f in result["after"]["validation"]["findings"]] == ["RULE-008"]
    assert result["after"]["validation"]["status"] == "warning"
    assert {(c["field"], c["old_value"], c["new_value"]) for c in result["applied"]} == {
        ("pa_obtained", "false", "true"),
        ("pa_number", None, "AUTH-7781"),
    }

    # Corrected values show everywhere: detail, list filters, and validation
    claim = client.get(f"/api/claims/{CLAIM}").json()
    assert (claim["pa_obtained"], claim["pa_number"], claim["has_corrections"]) == (
        True,
        "AUTH-7781",
        True,
    )
    missing = client.get("/api/claims", params={"missing_prior_auth": True}).json()
    assert CLAIM not in [c["claim_id"] for c in missing["items"]]
    assert client.get(f"/api/validate/{CLAIM}").json()["status"] == "warning"


def test_applying_both_fixes_passes_the_claim(client):
    apply(client, "RULE-002", {"pa_number": "AUTH-1"})
    result = apply(client, "RULE-008").json()
    assert result["after"]["validation"]["status"] == "pass"
    assert len(result["after"]["corrections"]) == 3


def test_undo_restores_source_values(client):
    apply(client, "RULE-002", {"pa_number": "AUTH-1"})
    body = client.delete(f"/api/aifix/{CLAIM}/corrections").json()
    assert body["validation"]["status"] == "error"
    assert body["corrections"] == []
    claim = client.get(f"/api/claims/{CLAIM}").json()
    assert (claim["pa_obtained"], claim["pa_number"], claim["has_corrections"]) == (
        False,
        None,
        False,
    )


def test_manual_and_clarify_suggestions_cannot_be_applied(client):
    assert apply(client, "appeal:DEN0000001").status_code == 422


def test_values_must_belong_to_the_fix(client):
    res = apply(client, "RULE-008", {"total_charge": "1"})
    assert res.status_code == 422
    assert "total_charge" in res.json()["detail"]


def test_unknown_claim_or_suggestion_is_404(client):
    assert client.get("/api/aifix/CLM9999999").status_code == 404
    assert apply(client, "RULE-999").status_code == 404
    assert client.delete("/api/aifix/CLM9999999/corrections").status_code == 404


def test_high_charge_review_cites_contract_rates(client):
    client.post(
        "/api/rules",
        json={
            "name": "Over $1,000",
            "category": "Billing",
            "severity": "warning",
            "conditions": [{"field": "total_charge", "operator": "greaterThan", "value": "1000"}],
        },
    )
    suggestion = by_id(fixes(client))["RULE-010"]
    assert suggestion["action"] == "manual"
    # E&M $1,000 at 90% + Surgery $1,500 at 95%
    assert "$2,325.00" in suggestion["reasoning"]
    contracts = [c["reference_id"] for c in suggestion["citations"] if c["source_type"] == "payer_contract"]
    assert contracts == ["CON0003", "CON0004"]


def test_diagnosis_fix_rejects_invalid_codes(client):
    client.post(
        "/api/rules",
        json={
            "name": "GERD specificity",
            "category": "Coding",
            "severity": "error",
            "conditions": [{"field": "primary_icd10", "operator": "contains", "value": "K21"}],
        },
    )
    suggestion = by_id(fixes(client))["RULE-010"]
    assert suggestion["clarification_topic"] == "medical_necessity"
    res = apply(client, "RULE-010", {"primary_icd10": "not-a-code"})
    assert res.status_code == 422
    assert res.json()["detail"] == "Primary ICD-10 must be an ICD-10 code such as E11.65 or I10"
    assert apply(client, "RULE-010", {"primary_icd10": "K21.9"}).status_code == 200


@pytest.mark.parametrize(
    ("condition", "title", "summary", "reasoning"),
    [
        (
            {"field": "days_in_ar", "operator": "greaterThan", "value": "30"},
            "Follow up with the payer on claim status",
            "The claim has been in AR for 45 days.",
            "This payer typically pays in 28 days.",
        ),
        (
            {"field": "days_to_submission", "operator": "greaterThan", "value": "3"},
            "Confirm the payer's timely filing limit",
            "Submitted 5 days after the service date.",
            "Claims filed after the payer's limit are denied",
        ),
    ],
)
def test_aging_rules_get_payer_follow_up(client, condition, title, summary, reasoning):
    client.post(
        "/api/rules",
        json={"name": "Aging", "category": "Billing", "severity": "warning", "conditions": [condition]},
    )
    suggestion = by_id(fixes(client))["RULE-010"]
    assert (suggestion["title"], suggestion["summary"]) == (title, summary)
    assert suggestion["reasoning"].startswith(reasoning)
    assert suggestion["action"] == "manual"
    assert ("payer", "PAY002") in {(c["source_type"], c["reference_id"]) for c in suggestion["citations"]}


def test_values_must_parse_as_the_field_type(client):
    res = apply(client, "RULE-002", {"pa_obtained": "maybe", "pa_number": "PA-1"})
    assert res.status_code == 422
    assert "maybe" in res.json()["detail"]


def test_custom_rule_gets_generic_suggestion(client):
    client.post(
        "/api/rules",
        json={
            "name": "Institutional check",
            "category": "Billing",
            "severity": "info",
            "recommended_action": "Confirm the bill type",
            "conditions": [{"field": "claim_type", "operator": "equals", "value": "Institutional"}],
        },
    )
    suggestion = by_id(fixes(client))["RULE-010"]
    assert suggestion["action"] == "manual"
    assert suggestion["steps"] == ["Confirm the bill type"]


def test_missing_diagnosis_derived_from_lines(repo):
    # Bypass model validation: source data always has a diagnosis, but rules may still check
    detail = repo.get_claim("CLM0000002")
    claim = ClaimDetail.model_construct(**{**dict(detail), "primary_icd10": ""})
    rule = Rule.model_validate(
        {
            "id": "RULE-001",
            "name": "Missing dx",
            "category": "Coding",
            "severity": "error",
            "conditions": [{"field": "primary_icd10", "operator": "isEmpty"}],
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }
    )
    validation = ClaimValidation.model_validate(
        {
            "claim_id": "CLM0000002",
            "status": "error",
            "risk_score": 25,
            "risk_factors": [],
            "findings": [
                {
                    "rule_id": "RULE-001",
                    "rule_name": "Missing dx",
                    "severity": "error",
                    "category": "Coding",
                    "message": "",
                    "recommended_action": "",
                }
            ],
        }
    )
    context = ClaimContext(
        claim=claim,
        validation=validation,
        rules={"RULE-001": rule},
        reference=ReferenceData.load(repo),
    )
    [suggestion, _appeal] = RuleBasedSuggester().suggest(context)
    assert suggestion.title == "Set primary diagnosis to K21.0"
    assert suggestion.confidence == "high"  # both lines point to K21.0
    assert suggestion.changes[0].suggested_value == "K21.0"


def test_correction_store_persists_and_clears(tmp_path):
    path = tmp_path / "corrections.json"
    store = CorrectionStore(path)
    store.add(CLAIM, f"{CLAIM}:RULE-008", {"is_clean_claim": ("false", "true")})
    store.add(CLAIM, f"{CLAIM}:RULE-008", {"is_clean_claim": ("true", "false")})

    reloaded = CorrectionStore(path)
    assert [c.id for c in reloaded.for_claim(CLAIM)] == ["COR-00001", "COR-00002"]
    assert reloaded.overrides() == {CLAIM: {"is_clean_claim": "false"}}  # latest wins

    assert len(reloaded.clear_claim(CLAIM)) == 2
    assert CorrectionStore(path).overrides() == {}
    assert CorrectionStore(path).add(CLAIM, "x", {"pa_number": (None, "A")})[0].id == "COR-00003"


@pytest.mark.parametrize("claim_id", ["CLM0000002", "CLM0000004"])
def test_overlay_round_trip_restores_originals(repo, claim_id):
    before = repo.claims_frame([claim_id]).iloc[0].to_dict()
    repo.apply_overrides({claim_id: {"is_clean_claim": "true", "pa_number": "Z1"}})
    row = repo.claims_frame([claim_id]).iloc[0]
    assert (row["is_clean_claim"], row["pa_number"], row["has_corrections"]) == (True, "Z1", True)
    repo.apply_overrides({})
    assert repo.claims_frame([claim_id]).iloc[0].to_dict() == before


def test_fix_that_changes_nothing_is_refused(client):
    client.post(
        "/api/rules",
        json={
            "name": "GERD specificity",
            "category": "Coding",
            "severity": "error",
            "conditions": [{"field": "primary_icd10", "operator": "contains", "value": "K21"}],
        },
    )
    res = apply(client, "RULE-010", {"primary_icd10": "K21.0"})  # the claim's current code
    assert res.status_code == 422
    assert res.json()["detail"] == (
        "Nothing to change: Primary ICD-10 is already K21.0. Enter a different value to apply."
    )
    assert fixes(client)["corrections"] == []
    assert client.get(f"/api/claims/{CLAIM}").json()["has_corrections"] is False

