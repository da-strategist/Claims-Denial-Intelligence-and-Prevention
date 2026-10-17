"""Risk scorer: each factor, the AR aging tiers, and the 100-point cap."""

import pytest

from app.models import RuleFinding, Severity
from app.services.risk_scorer import score_claim

# A claim with nothing that adds risk
LOW_RISK = {
    "days_in_ar": 10,
    "has_prior_denial": False,
    "has_prior_preventable_denial": False,
    "pa_required": False,
    "pa_obtained": False,
    "primary_icd10": "I10",
    "is_clean_claim": True,
}


def finding(severity, rule_id="RULE-001"):
    return RuleFinding(
        rule_id=rule_id,
        rule_name="x",
        severity=severity,
        category="Coding",
        message="",
        recommended_action="",
    )


def factors(findings=(), **changes):
    score, found = score_claim({**LOW_RISK, **changes}, list(findings))
    return score, {f.label: f.points for f in found}


def test_low_risk_claim_scores_zero():
    assert factors() == (0, {})


def test_rule_findings_by_severity():
    findings = [finding(Severity.ERROR), finding(Severity.WARNING), finding(Severity.WARNING)]
    findings.append(finding(Severity.INFO))  # info adds nothing
    assert factors(findings) == (45, {"1 rule error": 25, "2 rule warnings": 20})


@pytest.mark.parametrize(
    ("changes", "label", "points"),
    [
        ({"has_prior_denial": True}, "Patient has prior denials", 20),
        ({"pa_required": True}, "Missing prior authorization", 15),
        ({"primary_icd10": "  "}, "Missing primary diagnosis", 10),
        ({"is_clean_claim": False}, "Not a clean claim", 5),
    ],
)
def test_claim_attribute_factors(changes, label, points):
    assert factors(**changes) == (points, {label: points})


def test_preventable_denial_adds_to_denial_history():
    assert factors(has_prior_denial=True, has_prior_preventable_denial=True)[0] == 25
    # Without a prior denial the preventable flag can't apply
    assert factors(has_prior_preventable_denial=True)[0] == 0


def test_prior_auth_obtained_is_no_risk():
    assert factors(pa_required=True, pa_obtained=True)[0] == 0


@pytest.mark.parametrize(
    ("days_in_ar", "points"),
    [(30, 0), (31, 5), (60, 5), (61, 10), (90, 10), (91, 15)],
)
def test_ar_aging_tiers(days_in_ar, points):
    # Only the highest tier reached counts
    assert factors(days_in_ar=days_in_ar)[0] == points


def test_risk_score_is_capped_at_100():
    errors = [finding(Severity.ERROR, f"RULE-00{i}") for i in range(1, 4)]
    score, found = factors(
        errors,
        days_in_ar=120,
        has_prior_denial=True,
        has_prior_preventable_denial=True,
        pa_required=True,
        primary_icd10="",
        is_clean_claim=False,
    )
    assert score == 100
    assert sum(found.values()) > 100
