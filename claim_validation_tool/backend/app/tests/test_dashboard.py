"""Dashboard tests against the fixture claims.

    claim       service     payer   status  charge  allowed paid  days_in_ar  clean
    CLM0000001  2025-01-10  PAY001  Paid    100     90      80    10          yes
    CLM0000002  2025-02-15  PAY002  Denied  2500    0       0     45          no
    CLM0000003  2025-03-20  PAY001  Paid    800     700     650   20          yes
    CLM0000004  2025-03-20  PAY002  Denied  800     0       0     60          no
"""

import pytest


def dashboard(client, **params):
    res = client.get("/api/dashboard", params=params)
    assert res.status_code == 200, res.text
    return res.json()


def kpis(body):
    return {kpi["key"]: kpi for kpi in body["kpis"]}


def test_all_time_kpis(client):
    body = dashboard(client)
    assert body["period"] == {"start": "2025-01-10", "end": "2025-03-20"}
    assert body["comparison_period"] is None
    values = {key: kpi["value"] for key, kpi in kpis(body).items()}
    assert values == {
        "claims": 4,
        "denial_rate": 0.5,
        "clean_claim_rate": 0.5,
        "avg_days_in_ar": 33.75,
        "net_collection_rate": pytest.approx(730 / 790),
        "at_risk": 1,
    }
    assert all(kpi["previous"] is None for kpi in body["kpis"])
    assert kpis(body)["denial_rate"]["detail"] == "2 denied · $3.3K · 100% preventable"
    assert kpis(body)["denial_rate"]["higher_is_better"] is False
    assert kpis(body)["claims"]["higher_is_better"] is None


def test_trailing_months_compare_with_the_period_before(client):
    body = dashboard(client, months=1)
    assert body["period"] == {"start": "2025-03-01", "end": "2025-03-31"}
    assert body["comparison_period"] == {"start": "2025-02-01", "end": "2025-02-28"}
    claims = kpis(body)["claims"]
    assert (claims["value"], claims["previous"]) == (2, 1)
    assert kpis(body)["denial_rate"]["previous"] == 1.0


def test_comparison_dropped_when_no_earlier_claims(client):
    body = dashboard(client, months=3)
    assert body["comparison_period"] is None
    assert kpis(body)["claims"]["previous"] is None


def test_charts(client):
    body = dashboard(client)
    assert [(m["month"], m["claims"], m["paid"], m["denied"]) for m in body["revenue_trend"]] == [
        ("2025-01", 1, 80.0, 0.0),
        ("2025-02", 1, 0.0, 2500.0),
        ("2025-03", 2, 650.0, 800.0),
    ]
    # Most denials first, ties broken by amount
    assert [(r["category"], r["denials"], r["amount"]) for r in body["denial_reasons"]] == [
        ("Prior Authorization", 1, 2500.0),
        ("Coding Errors", 1, 800.0),
    ]
    assert [(b["label"], b["claims"]) for b in body["ar_aging"]] == [
        ("0–30", 2),
        ("31–60", 2),
        ("61–90", 0),
        ("90+", 0),
    ]
    assert sum(s["claims"] for s in body["validation_status"]) == 4
    assert [s["status"] for s in body["validation_status"]] == ["pass", "warning", "error", "aifix"]
    assert [(p["payer_name"], p["claims"], p["denial_rate"]) for p in body["payers"]] == [
        ("Medicare FFS", 2, 0.0),
        ("Blue Cross NC", 2, 1.0),
    ]


def test_payer_filter(client):
    body = dashboard(client, payer_id="PAY002")
    assert kpis(body)["claims"]["value"] == 2
    assert kpis(body)["denial_rate"]["value"] == 1.0
    assert [p["payer_id"] for p in body["payers"]] == ["PAY002"]


def test_filter_with_no_claims(client):
    body = dashboard(client, department_id="DEPT01")
    assert body["period"] is None
    assert kpis(body)["claims"]["value"] == 0
    assert body["revenue_trend"] == [] and body["payers"] == []


def test_at_risk_follows_rule_changes_and_fixes(client):
    assert kpis(dashboard(client))["at_risk"]["value"] == 1
    client.post(
        "/api/aifix/CLM0000002/apply",
        json={"suggestion_id": "CLM0000002:RULE-002", "values": {"pa_number": "AUTH-1"}},
    )
    assert kpis(dashboard(client))["at_risk"]["value"] == 0
    client.delete("/api/aifix/CLM0000002/corrections")
    client.patch("/api/rules/RULE-002", json={"enabled": False})
    assert kpis(dashboard(client))["at_risk"]["value"] == 0


@pytest.mark.parametrize("params", [{"months": 0}, {"months": 37}, {"payer_id": "nope"}])
def test_invalid_params_are_422(client, params):
    assert client.get("/api/dashboard", params=params).status_code == 422
