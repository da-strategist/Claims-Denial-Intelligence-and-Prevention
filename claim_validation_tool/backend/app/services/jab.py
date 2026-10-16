"""Catalog of the proposed ClaustraRCM <-> JAB Audit API contracts.

Each example is built as a model instance, so it is guaranteed to satisfy the schema
shown next to it. Example values are illustrative, not drawn from the claims data.
"""

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from app.models import RuleCreate, ValidationStatus
from app.models.jab import (
    ApiContract,
    ClaimHandoff,
    ContractField,
    Direction,
    FindingsBatch,
    HandoffAccepted,
    HandoffBatch,
    HandoffLine,
    RecoveryStatus,
    RecoveryUpdate,
    Remittance,
    RuleSuggestion,
    UnderpaymentFinding,
    VarianceReason,
)

WEBHOOK_NOTES = [
    "Signed with HMAC-SHA256 over the raw body (X-JAB-Signature); unsigned calls get 401.",
    "Idempotent on its ID: redelivery returns 200 without reprocessing.",
    "Returns 202 Accepted; processing is asynchronous.",
]

_HANDOFF = HandoffBatch(
    batch_id="HB-2026-01-07-001",
    sent_at=datetime(2026, 1, 7, 2, 0, tzinfo=UTC),
    claims=[
        ClaimHandoff(
            claim_id="CLM0104512",
            payer_id="PAY004",
            service_date=date(2025, 11, 18),
            adjudicated_on=date(2025, 12, 22),
            total_charge=Decimal("1650.00"),
            total_allowed=Decimal("1300.00"),
            total_paid=Decimal("1230.00"),
            lines=[
                HandoffLine(
                    line_id="LN00265310",
                    cpt_code="43239",
                    cpt_category="Surgery",
                    modifier="59",
                    units=1,
                    charge_amount=Decimal("1500.00"),
                    allowed_amount=Decimal("1210.00"),
                    paid_amount=Decimal("1150.00"),
                    contract_id="CON0044",
                    expected_reimbursement=Decimal("1425.00"),
                ),
                HandoffLine(
                    line_id="LN00265311",
                    cpt_code="99213",
                    cpt_category="E&M",
                    units=1,
                    charge_amount=Decimal("150.00"),
                    allowed_amount=Decimal("90.00"),
                    paid_amount=Decimal("80.00"),
                    contract_id="CON0041",
                    expected_reimbursement=Decimal("135.00"),
                ),
            ],
            remittance=Remittance(
                check_number="EFT8841207",
                check_date=date(2025, 12, 22),
                carc_codes=["45"],
                rarc_codes=["N381"],
            ),
            validation_status=ValidationStatus.PASS,
            risk_score=5,
            corrected_fields=["pa_number"],
        )
    ],
)

_FINDINGS = FindingsBatch(
    batch_id="FB-2026-01-09-014",
    findings=[
        UnderpaymentFinding(
            finding_id="UF-2026-000731",
            claim_id="CLM0104512",
            line_id="LN00265310",
            contract_id="CON0044",
            expected_amount=Decimal("1425.00"),
            paid_amount=Decimal("1150.00"),
            variance=Decimal("275.00"),
            reason=VarianceReason.RATE_MISMATCH,
            confidence=0.92,
            explanation=(
                "Paid at the 2024 surgical rate (76.7%); contract CON0044 sets 95% from 2025-01-01."
            ),
            appeal_deadline=date(2026, 6, 20),
        )
    ],
)

_RECOVERY = RecoveryUpdate(
    finding_id="UF-2026-000731",
    status=RecoveryStatus.RECOVERED,
    recovered_amount=Decimal("275.00"),
    updated_at=datetime(2026, 2, 14, 16, 30, tzinfo=UTC),
    note="Payer reprocessed at the contracted rate.",
)

_RULE_SUGGESTION = RuleSuggestion(
    suggestion_id="RS-2026-0012",
    rule=RuleCreate.model_validate(
        {
            "name": "Humana MA surgical rate check",
            "description": "Humana MA has underpaid institutional surgical claims at the 2024 rate.",
            "category": "Payer-Specific",
            "severity": "warning",
            "enabled": False,
            "recommended_action": "Confirm the 2025 contract rate is loaded before submitting.",
            "scope": {"type": "payer", "values": ["PAY004"]},
            "conditions": [
                {"field": "claim_type", "operator": "equals", "value": "Institutional"},
                {"field": "total_charge", "operator": "greaterThan", "value": "1000"},
            ],
        }
    ),
    evidence_finding_ids=["UF-2026-000731", "UF-2026-000744", "UF-2026-000802"],
    claims_affected=38,
    amount_at_stake=Decimal("9412.50"),
)


def flatten_schema(schema: dict[str, Any]) -> list[ContractField]:
    """Flatten a Pydantic JSON Schema into one row per field, nested paths included."""
    defs = schema.get("$defs", {})

    def resolve(node: dict[str, Any]) -> dict[str, Any]:
        ref = node.get("$ref")
        if not ref:
            return node
        siblings = {key: value for key, value in node.items() if key != "$ref"}
        return {**defs[ref.rsplit("/", 1)[-1]], **siblings}

    def unwrap(node: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """Drop the null branch of Optional fields; returns (schema, nullable)."""
        options = node.get("anyOf")
        if not options:
            return resolve(node), False
        kept = [option for option in options if option.get("type") != "null"]
        nullable = len(kept) < len(options)
        if {option.get("type") for option in kept} == {"number", "string"}:
            return {"type": "decimal", **_meta(node)}, nullable  # Decimal: number or string
        if len(kept) == 1:
            return {**resolve(kept[0]), **_meta(node)}, nullable
        return {"type": " | ".join(_type_name(resolve(o)) for o in kept), **_meta(node)}, nullable

    def walk(node: dict[str, Any], prefix: str) -> Iterator[ContractField]:
        required = set(node.get("required", []))
        for name, raw in node.get("properties", {}).items():
            field, nullable = unwrap(raw)
            path = f"{prefix}{name}"
            yield ContractField(
                path=path,
                type=_type_name(field) + (" | null" if nullable else ""),
                required=name in required,
                description=field.get("description"),
                allowed_values=[str(v) for v in field["enum"]] if "enum" in field else None,
                pattern=field.get("pattern"),
            )
            if field.get("type") == "object" or "properties" in field:
                yield from walk(field, f"{path}.")
            items = resolve(field.get("items", {})) if field.get("type") == "array" else {}
            if "properties" in items:
                yield from walk(items, f"{path}[].")

    return list(walk(resolve(schema), ""))


def _meta(node: dict[str, Any]) -> dict[str, Any]:
    return {key: node[key] for key in ("description", "pattern") if key in node}


def _type_name(node: dict[str, Any]) -> str:
    if "enum" in node:
        return "enum"
    kind = node.get("type", "any")
    if kind == "string" and node.get("format") in ("date", "date-time"):
        return node["format"]
    if kind == "array":
        items = node.get("items", {})
        return f"{'object' if '$ref' in items or 'properties' in items else _type_name(items)}[]"
    return kind


def _contract(
    *,
    id: str,
    title: str,
    direction: Direction,
    method: str,
    path: str,
    purpose: str,
    request: BaseModel,
    response: type[BaseModel] | None = None,
    notes: list[str],
) -> ApiContract:
    return ApiContract(
        id=id,
        title=title,
        direction=direction,
        method=method,
        path=path,
        purpose=purpose,
        request_model=type(request).__name__,
        request_fields=flatten_schema(type(request).model_json_schema()),
        request_schema=type(request).model_json_schema(),
        request_example=request.model_dump(mode="json", exclude_none=True),
        response_model=response.__name__ if response else None,
        response_schema=response.model_json_schema() if response else None,
        notes=notes,
    )


def list_contracts() -> list[ApiContract]:
    return [
        _contract(
            id="claim-handoff",
            title="Claim handoff",
            direction=Direction.OUTBOUND,
            method="POST",
            path="{JAB_AUDIT_URL}/v1/claims/handoff",
            purpose="Send adjudicated claims nightly, with the contract rate and the validation "
            "context JAB Audit can't see on its own.",
            request=_HANDOFF,
            response=HandoffAccepted,
            notes=[
                "Nightly batch of claims whose 835 remittance posted that day; up to 500 per call.",
                "batch_id is the idempotency key.",
                "IDs and amounts only — no patient demographics "
                "(HIPAA minimum necessary; BAA required).",
            ],
        ),
        _contract(
            id="underpayment-findings",
            title="Underpayment findings",
            direction=Direction.INBOUND,
            method="POST",
            path="/api/jab/webhooks/findings",
            purpose="JAB Audit reports lines paid below contract, so billing specialists see "
            "them on the claim in the workbench.",
            request=_FINDINGS,
            notes=WEBHOOK_NOTES,
        ),
        _contract(
            id="recovery-status",
            title="Recovery status",
            direction=Direction.INBOUND,
            method="POST",
            path="/api/jab/webhooks/recovery",
            purpose="Track each finding through appeal to recovery, so the dashboard can "
            "report recovered revenue.",
            request=_RECOVERY,
            notes=WEBHOOK_NOTES,
        ),
        _contract(
            id="rule-suggestions",
            title="Rule suggestions",
            direction=Direction.INBOUND,
            method="POST",
            path="/api/jab/webhooks/rule-suggestions",
            purpose="Close the loop: recurring underpayment patterns become pre-submission "
            "rules, using the same rule format as Rule Manager.",
            request=_RULE_SUGGESTION,
            notes=[
                *WEBHOOK_NOTES,
                "Creates the rule disabled; a person reviews it in Rule Manager before enabling.",
            ],
        ),
    ]
