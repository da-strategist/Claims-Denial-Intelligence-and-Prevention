NEW_RULE = {
    "name": "Medicaid ER visit",
    "category": "Payer-Specific",
    "severity": "warning",
    "scope": {"type": "payer", "values": ["PAY001"]},
    "conditions": [{"field": "place_of_service", "operator": "equals", "value": "23"}],
}


def test_list_rules_returns_seed_set(client):
    rules = client.get("/api/rules").json()
    assert len(rules) == 9
    assert rules[0]["id"] == "RULE-001"


def test_list_rule_fields(client):
    fields = {f["field"]: f for f in client.get("/api/rules/fields").json()}
    assert fields["total_charge"]["type"] == "number"
    assert fields["claim_type"]["options"] == ["Professional", "Institutional"]


def test_create_get_and_delete_rule(client):
    created = client.post("/api/rules", json=NEW_RULE)
    assert created.status_code == 201
    rule = created.json()
    assert rule["id"] == "RULE-010"
    assert rule["enabled"] is True

    assert client.get("/api/rules/RULE-010").json()["name"] == "Medicaid ER visit"
    assert client.delete("/api/rules/RULE-010").status_code == 204
    assert client.get("/api/rules/RULE-010").status_code == 404


def test_patch_changes_only_sent_fields(client):
    before = client.get("/api/rules/RULE-002").json()
    after = client.patch("/api/rules/RULE-002", json={"enabled": False}).json()
    assert after["enabled"] is False
    assert after["conditions"] == before["conditions"]
    assert after["updated_at"] > before["updated_at"]
    assert after["created_at"] == before["created_at"]


def test_put_replaces_rule(client):
    rule = client.put("/api/rules/RULE-001", json=NEW_RULE).json()
    assert rule["id"] == "RULE-001"
    assert rule["name"] == "Medicaid ER visit"
    assert rule["scope"] == {"type": "payer", "values": ["PAY001"]}


def test_invalid_rule_is_422(client):
    bad = {**NEW_RULE, "conditions": [{"field": "pa_required", "operator": "contains", "value": "x"}]}
    assert client.post("/api/rules", json=bad).status_code == 422
    assert client.patch("/api/rules/RULE-001", json={"conditions": []}).status_code == 422


def test_unknown_rule_is_404(client):
    assert client.get("/api/rules/RULE-999").status_code == 404
    assert client.patch("/api/rules/RULE-999", json={"enabled": False}).status_code == 404
    assert client.put("/api/rules/RULE-999", json=NEW_RULE).status_code == 404
    assert client.delete("/api/rules/RULE-999").status_code == 404


def test_test_draft_rule(client):
    draft = {"conditions": [{"field": "status", "operator": "equals", "value": "Denied"}]}
    result = client.post("/api/rules/test", json=draft).json()
    assert result == {
        "total_claims": 4,
        "in_scope": 4,
        "matched": 2,
        "sample_claim_ids": ["CLM0000002", "CLM0000004"],
    }


def test_validate_claims(client):
    results = client.post(
        "/api/validate", json={"claim_ids": ["CLM0000004", "CLM0000001", "CLM0000004"]}
    ).json()
    # Order preserved, duplicates dropped
    assert [r["claim_id"] for r in results] == ["CLM0000004", "CLM0000001"]
    assert [r["status"] for r in results] == ["warning", "pass"]


def test_validate_with_chosen_rules(client):
    [result] = client.post(
        "/api/validate", json={"claim_ids": ["CLM0000002"], "rule_ids": ["RULE-002"]}
    ).json()
    assert [f["rule_id"] for f in result["findings"]] == ["RULE-002"]


def test_validate_respects_disabled_rules(client):
    client.patch("/api/rules/RULE-008", json={"enabled": False})
    result = client.get("/api/validate/CLM0000004").json()
    assert result["findings"] == []
    assert result["status"] == "pass"


def test_validate_unknown_ids_are_404(client):
    assert client.post("/api/validate", json={"claim_ids": ["CLM9999999"]}).status_code == 404
    assert client.get("/api/validate/CLM9999999").status_code == 404
    res = client.post("/api/validate", json={"claim_ids": ["CLM0000001"], "rule_ids": ["RULE-999"]})
    assert res.status_code == 404


def test_validate_request_limits(client):
    assert client.post("/api/validate", json={"claim_ids": []}).status_code == 422
    too_many = [f"CLM{n:07d}" for n in range(201)]
    assert client.post("/api/validate", json={"claim_ids": too_many}).status_code == 422


def test_rule_fields_list_valid_operators(client):
    fields = {f["field"]: f for f in client.get("/api/rules/fields").json()}
    assert fields["is_clean_claim"]["operators"] == ["equals", "notEquals"]
    assert "contains" in fields["primary_icd10"]["operators"]
    assert "greaterThan" not in fields["primary_icd10"]["operators"]


def test_list_departments(client):
    names = [d["department_name"] for d in client.get("/api/departments").json()]
    assert names == ["Internal Medicine", "Gastroenterology"]
