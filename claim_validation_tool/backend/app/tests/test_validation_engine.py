"""Validation engine tests against the fixture claims.

Fixture claims at a glance:
  CLM0000001  PAT000001  PAY001  Paid    Professional   $100   clean      I10    10 days AR
  CLM0000002  PAT000002  PAY002  Denied  Institutional  $2500  not clean  K21.0  45 days AR  PA required, not obtained
  CLM0000003  PAT000002  PAY001  Paid    Institutional  $800   clean      J06.9  20 days AR  PA obtained (PA123456)
  CLM0000004  PAT000001  PAY002  Denied  Professional   $800   not clean  I10    60 days AR

CLM0000002's preventable denial (2025-03-10) predates CLM0000003's submission (2025-03-21),
so CLM0000003 carries patient denial history. No claim counts its own denial.
"""

from datetime import UTC, datetime

import pytest

from app.data.rules import RuleRepository
from app.data.seed_rules import DEFAULT_RULES
from app.models import Rule, RuleCreate, RuleDefinition, ValidationStatus
from app.services import validation_engine


def matches(repo, conditions, logic="AND", scope=None) -> set[str]:
    rule = RuleDefinition(conditions=conditions, condition_logic=logic, scope=scope or {})
    claims = repo.claims_frame()
    return set(claims.loc[validation_engine.rule_mask(rule, claims), "claim_id"])


def make_rule(rule_id="RULE-001", **overrides) -> Rule:
    fields = {
        "name": "Test rule",
        "category": "Billing",
        "severity": "error",
        "conditions": [{"field": "total_charge", "operator": "greaterThan", "value": "0"}],
        **overrides,
    }
    now = datetime.now(UTC)
    return Rule(**fields, id=rule_id, created_at=now, updated_at=now)


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        ({"field": "pa_number", "operator": "isEmpty"}, {"CLM0000001", "CLM0000002", "CLM0000004"}),
        ({"field": "pa_number", "operator": "isNotEmpty"}, {"CLM0000003"}),
        ({"field": "primary_icd10", "operator": "equals", "value": "I10"}, {"CLM0000001", "CLM0000004"}),
        ({"field": "payer_id", "operator": "notEquals", "value": "PAY001"}, {"CLM0000002", "CLM0000004"}),
        ({"field": "total_charge", "operator": "greaterThan", "value": "800"}, {"CLM0000002"}),
        ({"field": "total_charge", "operator": "lessThan", "value": 800}, {"CLM0000001"}),
        ({"field": "total_charge", "operator": "equals", "value": "800.00"}, {"CLM0000003", "CLM0000004"}),
        ({"field": "days_in_ar", "operator": "greaterThan", "value": "59"}, {"CLM0000004"}),
        ({"field": "service_date", "operator": "greaterThan", "value": "2025-03-01"}, {"CLM0000003", "CLM0000004"}),
        ({"field": "service_date", "operator": "lessThan", "value": "2025-02-15"}, {"CLM0000001"}),
        ({"field": "primary_icd10", "operator": "contains", "value": ".9"}, {"CLM0000003"}),
        ({"field": "primary_icd10", "operator": "contains", "value": "k21"}, {"CLM0000002"}),
        ({"field": "is_clean_claim", "operator": "equals", "value": "false"}, {"CLM0000002", "CLM0000004"}),
        ({"field": "pa_obtained", "operator": "equals", "value": True}, {"CLM0000003"}),
        ({"field": "claim_type", "operator": "equals", "value": "Institutional"}, {"CLM0000002", "CLM0000003"}),
        ({"field": "days_to_submission", "operator": "greaterThan", "value": "4"}, {"CLM0000002", "CLM0000004"}),
    ],
)
def test_operators(repo, condition, expected):
    assert matches(repo, [condition]) == expected


def test_and_logic_requires_every_condition(repo):
    conditions = [
        {"field": "pa_required", "operator": "equals", "value": "true"},
        {"field": "pa_obtained", "operator": "equals", "value": "false"},
    ]
    assert matches(repo, conditions, "AND") == {"CLM0000002"}


def test_or_logic_requires_any_condition(repo):
    conditions = [
        {"field": "total_charge", "operator": "greaterThan", "value": "1000"},
        {"field": "primary_icd10", "operator": "equals", "value": "J06.9"},
    ]
    assert matches(repo, conditions, "OR") == {"CLM0000002", "CLM0000003"}


@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        ({"type": "all"}, {"CLM0000001", "CLM0000004"}),
        ({"type": "payer", "values": ["PAY002"]}, {"CLM0000004"}),
        ({"type": "payer", "values": ["PAY001", "PAY002"]}, {"CLM0000001", "CLM0000004"}),
        ({"type": "claim_type", "values": ["Institutional"]}, set()),
        ({"type": "department", "values": ["DEPT02"]}, {"CLM0000001"}),
    ],
)
def test_scope_limits_which_claims_a_rule_applies_to(repo, scope, expected):
    conditions = [{"field": "primary_icd10", "operator": "equals", "value": "I10"}]
    assert matches(repo, conditions, scope=scope) == expected


@pytest.mark.parametrize(
    "condition",
    [
        {"field": "not_a_field", "operator": "equals", "value": "x"},
        {"field": "pa_required", "operator": "greaterThan", "value": "1"},
        {"field": "total_charge", "operator": "contains", "value": "1"},
        {"field": "claim_type", "operator": "equals", "value": "Dental"},
        {"field": "total_charge", "operator": "greaterThan", "value": "lots"},
        {"field": "service_date", "operator": "lessThan", "value": "03/01/2025"},
        {"field": "is_clean_claim", "operator": "equals", "value": "yes"},
        {"field": "total_charge", "operator": "greaterThan"},
    ],
)
def test_invalid_conditions_are_rejected(condition):
    with pytest.raises(ValueError):
        RuleDefinition(conditions=[condition])


def test_scope_other_than_all_needs_values():
    with pytest.raises(ValueError):
        RuleDefinition(
            scope={"type": "payer"},
            conditions=[{"field": "pa_number", "operator": "isEmpty"}],
        )


def test_seed_rules_on_fixture_claims(repo):
    results = validation_engine.validate_claims(repo.claims_frame(), RuleRepository().list())
    by_id = {result.claim_id: result for result in results}

    assert [result.claim_id for result in results] == [
        "CLM0000001",
        "CLM0000002",
        "CLM0000003",
        "CLM0000004",
    ]
    assert by_id["CLM0000001"].status == ValidationStatus.PASS
    assert by_id["CLM0000001"].risk_score == 0

    # No rule findings, but the patient's earlier preventable denial adds risk
    claim3 = by_id["CLM0000003"]
    assert claim3.status == ValidationStatus.PASS
    assert [(f.label, f.points) for f in claim3.risk_factors] == [
        ("Patient has prior denials", 20),
        ("Prior denial was preventable", 5),
    ]

    # Missing PA (error) + non-clean (warning), AR aging, missing PA, non-clean.
    # Its own denial is not denial history, which leaves it exactly at the AI fix threshold.
    claim2 = by_id["CLM0000002"]
    assert {f.rule_name for f in claim2.findings} == {
        "Missing Prior Authorization",
        "Non-Clean Claim Review",
    }
    assert claim2.risk_score == 25 + 10 + 5 + 15 + 5
    assert claim2.status == ValidationStatus.AI_FIX

    # Warnings only: non-clean; 60 days in AR is not *over* 60, so no AR rule
    claim4 = by_id["CLM0000004"]
    assert [f.rule_name for f in claim4.findings] == ["Non-Clean Claim Review"]
    assert claim4.status == ValidationStatus.WARNING


def test_disabled_rules_are_skipped(repo):
    rule = make_rule(enabled=False)
    results = validation_engine.validate_claims(repo.claims_frame(), [rule])
    assert all(result.findings == [] for result in results)


def test_error_below_ai_fix_threshold_is_error(repo):
    claims = repo.claims_frame(["CLM0000001"])
    [result] = validation_engine.validate_claims(claims, [make_rule()])
    assert result.risk_score == 25
    assert result.status == ValidationStatus.ERROR


def test_info_findings_do_not_change_status_or_score(repo):
    claims = repo.claims_frame(["CLM0000001"])
    [result] = validation_engine.validate_claims(claims, [make_rule(severity="info")])
    assert len(result.findings) == 1
    assert result.status == ValidationStatus.PASS
    assert result.risk_score == 0


def test_rule_test_counts_scope_and_matches(repo):
    rule = RuleDefinition(
        scope={"type": "payer", "values": ["PAY002"]},
        conditions=[{"field": "is_clean_claim", "operator": "equals", "value": "false"}],
    )
    result = validation_engine.test_rule(rule, repo.claims_frame())
    assert (result.total_claims, result.in_scope, result.matched) == (4, 2, 2)
    assert result.sample_claim_ids == ["CLM0000002", "CLM0000004"]


def test_seed_rules_are_valid():
    assert len(DEFAULT_RULES) == 9
    assert all(isinstance(rule, RuleCreate) for rule in DEFAULT_RULES)
