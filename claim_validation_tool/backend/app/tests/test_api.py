def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_list_claims(client):
    body = client.get("/api/claims", params={"status": "Denied", "page_size": 1}).json()
    assert body["total"] == 2
    assert body["pages"] == 2
    assert len(body["items"]) == 1


def test_needs_attention_lists_claims_with_errors_by_risk(client):
    every_id = [claim["claim_id"] for claim in client.get("/api/claims").json()["items"]]
    validations = client.post("/api/validate", json={"claim_ids": every_id}).json()
    statuses = {v["claim_id"]: v for v in validations}
    at_risk = {cid for cid, v in statuses.items() if v["status"] in ("error", "aifix")}
    assert at_risk  # the fixture data has at least one

    body = client.get(
        "/api/claims", params={"needs_attention": True, "sort_by": "risk_score"}
    ).json()
    ids = [claim["claim_id"] for claim in body["items"]]
    assert set(ids) == at_risk
    risks = [statuses[cid]["risk_score"] for cid in ids]
    assert risks == sorted(risks, reverse=True)

    rest = client.get("/api/claims", params={"needs_attention": False}).json()
    assert body["total"] + rest["total"] == client.get("/api/claims").json()["total"]


def test_get_claim(client):
    body = client.get("/api/claims/CLM0000004").json()
    assert body["lines"][0]["modifier"] == "25"
    assert body["denials"][0]["root_cause_category"] == "Coding Errors"


def test_unknown_claim_is_404(client):
    res = client.get("/api/claims/CLM9999999")
    assert res.status_code == 404
    assert res.json()["detail"] == "Claim CLM9999999 not found"


def test_malformed_claim_id_is_422(client):
    assert client.get("/api/claims/not-a-claim").status_code == 422


def test_invalid_query_params_are_422(client):
    for params in ({"status": "Approved"}, {"page_size": 500}, {"sort_by": "patient_id"}):
        assert client.get("/api/claims", params=params).status_code == 422


def test_list_payers(client):
    assert [payer["payer_id"] for payer in client.get("/api/payers").json()] == [
        "PAY001",
        "PAY002",
        "PAY010",
    ]
