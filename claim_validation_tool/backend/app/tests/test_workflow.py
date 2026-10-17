"""End-to-end: one claim through the billing specialist's workflow, endpoint by endpoint.

Find the patient -> enter the claim -> it's flagged -> apply the AI fix -> submit ->
it ages in AR until overdue, with the workbench, rules, and dashboard following along.
"""

from datetime import date


def kpis(client):
    return {k["key"]: k for k in client.get("/api/dashboard").json()["kpis"]}


def test_claim_from_entry_to_overdue(client, today):
    # 1. Registration: the patient is found by name, with their primary payer
    patient = client.get("/api/patients", params={"search": "donald davis"}).json()["items"][0]
    assert (patient["patient_id"], patient["primary_payer_id"]) == ("PAT000003", "PAY001")

    # 2. The form's pick lists
    provider = client.get("/api/providers").json()[0]
    procedures = {p["cpt_code"]: p for p in client.get("/api/codes/procedures").json()}
    assert "99213" in procedures

    # 3. Entry: prior auth is required but wasn't obtained, so the draft is flagged
    res = client.post(
        "/api/claims",
        json={
            "patient_id": patient["patient_id"],
            "payer_id": patient["primary_payer_id"],
            "provider_id": provider["provider_id"],
            "diagnoses": ["E11.65"],
            "lines": [{"cpt_code": "99213", "units": 2, "icd10_pointer": "E11.65"}],
            "claim_type": "Professional",
            "service_date": "2026-01-05",
            "submission_date": "2026-01-06",
            "pa_required": True,
        },
    )
    assert res.status_code == 201, res.text
    claim, validation = res.json()["claim"], res.json()["validation"]
    claim_id = claim["claim_id"]
    assert claim["status"] == "Draft"
    assert claim["total_charge"] == 2 * procedures["99213"]["standard_charge"]
    assert validation["status"] == "error"
    assert "Missing prior authorization" in [f["label"] for f in validation["risk_factors"]]
    assert kpis(client)["claims"]["detail"].endswith("1 draft")

    # 4. The workbench lists it with the other drafts; submitting is blocked
    drafts = client.get("/api/claims", params={"status": "Draft"}).json()
    assert [c["claim_id"] for c in drafts["items"]] == [claim_id]
    blocked = client.post(f"/api/claims/{claim_id}/submit")
    assert blocked.status_code == 422

    # 5. AI Fix: record the auth number; the claim re-validates without the error
    suggestion = next(
        s for s in client.get(f"/api/aifix/{claim_id}").json()["suggestions"] if s["rule_id"] == "RULE-002"
    )
    applied = client.post(
        f"/api/aifix/{claim_id}/apply",
        json={"suggestion_id": suggestion["id"], "values": {"pa_number": "AUTH-42"}},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["after"]["validation"]["status"] == "warning"  # non-clean remains
    assert client.get(f"/api/claims/{claim_id}").json()["has_corrections"] is True

    # 6. Submission: Pending from today, no longer a draft
    submitted = client.post(f"/api/claims/{claim_id}/submit").json()["claim"]
    assert (submitted["status"], submitted["submission_date"]) == ("Pending", "2026-01-10")
    assert kpis(client)["claims"]["detail"].endswith("1 pending")

    # 7. Aging: past Medicare's 32 days to pay it's overdue, and the workbench can find it
    today(date(2026, 2, 15))
    claim = client.get(f"/api/claims/{claim_id}").json()
    assert (claim["days_in_ar"], claim["is_overdue"]) == (36, True)
    overdue = client.get("/api/claims", params={"overdue": True}).json()["items"]
    assert [c["claim_id"] for c in overdue] == [claim_id]
    assert kpis(client)["avg_days_in_ar"]["detail"].endswith("1 pending overdue")

    # 8. The patient's history now includes it
    assert client.get(f"/api/patients/{patient['patient_id']}").json()["claim_count"] == 1
