"""JAB Audit contract catalog: examples must satisfy their own schemas."""

import pytest
from pydantic import ValidationError

from app.models.jab import (
    FindingsBatch,
    HandoffBatch,
    RecoveryUpdate,
    RuleSuggestion,
    UnderpaymentFinding,
)
from app.services.jab import flatten_schema, list_contracts

MODELS = {
    "HandoffBatch": HandoffBatch,
    "FindingsBatch": FindingsBatch,
    "RecoveryUpdate": RecoveryUpdate,
    "RuleSuggestion": RuleSuggestion,
}


def test_contract_catalog(client):
    contracts = client.get("/api/jab/contracts").json()
    assert [(c["id"], c["direction"]) for c in contracts] == [
        ("claim-handoff", "outbound"),
        ("underpayment-findings", "inbound"),
        ("recovery-status", "inbound"),
        ("rule-suggestions", "inbound"),
    ]
    assert contracts[0]["response_model"] == "HandoffAccepted"


@pytest.mark.parametrize("contract", list_contracts(), ids=lambda c: c.id)
def test_examples_round_trip_through_their_models(contract):
    # The JSON example as sent on the wire must parse back into the request model
    model = MODELS[contract.request_model]
    parsed = model.model_validate(contract.request_example)
    assert parsed.model_dump(mode="json", exclude_none=True) == contract.request_example


def test_suggested_rules_arrive_disabled():
    suggestion = next(c for c in list_contracts() if c.id == "rule-suggestions")
    assert suggestion.request_example["rule"]["enabled"] is False


def test_money_is_exact_on_the_wire():
    handoff = next(c for c in list_contracts() if c.id == "claim-handoff")
    line = handoff.request_example["claims"][0]["lines"][0]
    assert line["expected_reimbursement"] == "1425.00"


def test_finding_rejects_bad_ids_and_confidence():
    base = {
        "finding_id": "UF-1",
        "claim_id": "CLM0000001",
        "expected_amount": "10.00",
        "paid_amount": "5.00",
        "variance": "5.00",
        "reason": "rate_mismatch",
        "confidence": 0.5,
        "explanation": "x",
    }
    UnderpaymentFinding.model_validate(base)
    for bad in ({"claim_id": "123"}, {"confidence": 1.5}, {"reason": "guess"}):
        with pytest.raises(ValidationError):
            UnderpaymentFinding.model_validate({**base, **bad})


def test_flatten_schema_paths_and_types():
    fields = {f.path: f for f in flatten_schema(HandoffBatch.model_json_schema())}
    assert fields["claims"].type == "object[]"
    assert fields["claims[].lines[].contract_id"].type == "string | null"
    assert fields["claims[].lines[].contract_id"].required is False
    assert fields["claims[].total_paid"].type == "decimal"
    assert fields["claims[].service_date"].type == "date"
    assert fields["claims[].validation_status"].allowed_values == [
        "pass",
        "warning",
        "error",
        "aifix",
    ]
    assert fields["claims[].remittance.carc_codes"].type == "string[]"
