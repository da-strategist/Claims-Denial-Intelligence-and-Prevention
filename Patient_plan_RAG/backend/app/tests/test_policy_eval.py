"""Regression gate for the multi-policy eval (see policy_eval.py).

THRESHOLDS are the minimum passes per policy and metric. They are a ratchet:
raise them when the pipeline improves, never lower them to make a change pass.
Run `python -m backend.app.tests.policy_eval` for the full scorecard.
"""

import pytest

from backend.app.tests import policy_eval

METRICS = ("metadata", "retrieval_top1", "retrieval_top3", "section_top1", "coverage", "summary")

THRESHOLDS = {
    "apex_health_gold_ppo_2025.pdf":              (5, 8, 8, 8, 3, 6),
    "summit_care_silver_hmo_2026.pdf":            (5, 9, 10, 9, 4, 6),
    "northwind_bronze_hdhp_2026.pdf":             (5, 10, 10, 10, 4, 5),
    # retrieval_top1 was 10 at baseline only because the handbook's question
    # headings were undetected and it was a few giant unlabelled chunks (the
    # top hit "contained" every answer while section_top1 was 0/10). With real
    # sections it is 8 and section_top1 8/10; the misses are noted in CLAUDE.md.
    "riverbend_community_care_medicaid_2025.pdf": (5, 8, 10, 8, 4, 5),
}


def test_scenarios_match_policy_text():
    assert policy_eval.validate_scenarios() == []


@pytest.fixture(scope="module")
def scores():
    for f in THRESHOLDS:
        if not (policy_eval.POLICY_DIR / f).exists():
            pytest.skip(f"{f} missing; run python -m synthetic_data.generate_policy")
    return {s.name: s for s in policy_eval.score_all()}


def test_every_scenario_policy_has_thresholds():
    assert set(THRESHOLDS) == set(policy_eval.SCENARIOS)


@pytest.mark.parametrize("policy", THRESHOLDS)
def test_policy_meets_thresholds(policy, scores):
    s = scores[policy]
    below = [
        f"{m}: {getattr(s, m)[0]}/{getattr(s, m)[1]} < {minimum}"
        for m, minimum in zip(METRICS, THRESHOLDS[policy])
        if getattr(s, m)[0] < minimum
    ]
    assert not below, "\n".join(below + ["failures:"] + s.failures)
