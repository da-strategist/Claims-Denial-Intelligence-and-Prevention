"""Composite denial-risk score (0-100) for a claim, with the factors that produced it.

Weights follow PROJECT_GUIDE.md: rule findings carry most of the weight, and claim
attributes that correlate with denials (prior denials, AR aging, missing prior auth,
missing diagnosis) add to it.

The same fact never counts twice: whether a claim is clean is scored only through rules
(the seed rule Non-Clean Claim Review), and the missing prior auth and missing diagnosis
factors are skipped when a rule that tests that field already flagged the claim (e.g.
Missing Prior Authorization). They still count if no such rule is enabled.

Denial history means the patient's earlier denials that were known when this claim
was submitted, never the claim's own denial, so the score reflects pre-submission risk.
"""

from collections.abc import Collection, Mapping
from typing import Any

from app.models import RiskFactor, RuleFinding, Severity

MAX_SCORE = 100

POINTS_PER_ERROR = 25
POINTS_PER_WARNING = 10
DENIAL_HISTORY_POINTS = 20
PREVENTABLE_DENIAL_POINTS = 5
MISSING_PRIOR_AUTH_POINTS = 15
MISSING_DIAGNOSIS_POINTS = 10

# (days in AR above which the points apply, points), checked highest first
AR_AGING_TIERS = [(90, 15), (60, 10), (30, 5)]


def score_claim(
    claim: Mapping[str, Any],
    findings: list[RuleFinding],
    flagged_fields: Collection[str] = (),
) -> tuple[int, list[RiskFactor]]:
    """Score one claim. `claim` is a row from ClaimsRepository.claims_frame();
    `flagged_fields` are the fields tested by the rules that flagged it."""
    factors: list[RiskFactor] = []

    errors = sum(1 for f in findings if f.severity == Severity.ERROR)
    warnings = sum(1 for f in findings if f.severity == Severity.WARNING)
    if errors:
        factors.append(_factor(f"{errors} rule error{'s' * (errors > 1)}", errors * POINTS_PER_ERROR))
    if warnings:
        factors.append(
            _factor(f"{warnings} rule warning{'s' * (warnings > 1)}", warnings * POINTS_PER_WARNING)
        )

    if claim["has_prior_denial"]:
        factors.append(_factor("Patient has prior denials", DENIAL_HISTORY_POINTS))
        if claim["has_prior_preventable_denial"]:
            factors.append(_factor("Prior denial was preventable", PREVENTABLE_DENIAL_POINTS))

    for threshold, points in AR_AGING_TIERS:
        if claim["days_in_ar"] > threshold:
            factors.append(_factor(f"Over {threshold} days in AR", points))
            break

    missing_pa = claim["pa_required"] and not claim["pa_obtained"]
    if missing_pa and "pa_obtained" not in flagged_fields:
        factors.append(_factor("Missing prior authorization", MISSING_PRIOR_AUTH_POINTS))
    if not str(claim["primary_icd10"]).strip() and "primary_icd10" not in flagged_fields:
        factors.append(_factor("Missing primary diagnosis", MISSING_DIAGNOSIS_POINTS))

    score = min(sum(f.points for f in factors), MAX_SCORE)
    return score, factors


def _factor(label: str, points: int) -> RiskFactor:
    return RiskFactor(label=label, points=points)
