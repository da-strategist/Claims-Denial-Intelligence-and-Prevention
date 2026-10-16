"""Proposed API contracts between ClaustraRCM and JAB Audit (underpayment recovery).

Conceptual: nothing here is wired to a live system. The payload models are real so
the design is type-checked, rendered as JSON Schema for the JAB Audit page, and
ready to implement. Payloads carry IDs and amounts only — no patient demographics
(HIPAA minimum necessary).
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, Field

from app.models.common import ClaimId, CptCode, LineId, PayerId, Ratio
from app.models.rule import RuleCreate, ValidationStatus

# Money in contracts is exact: decimal strings on the wire, never floats
Amount = Annotated[Decimal, Field(ge=0, decimal_places=2)]
SignedAmount = Annotated[Decimal, Field(decimal_places=2)]
ContractId = Annotated[str, Field(pattern=r"^CON\d{4}$")]
FindingId = Annotated[str, Field(pattern=r"^UF-[A-Z0-9-]+$")]


# --- 1. Claim handoff (ClaustraRCM -> JAB Audit) ------------------------------------


class HandoffLine(BaseModel):
    line_id: LineId
    cpt_code: CptCode
    cpt_category: str
    modifier: str | None = None
    units: int = Field(ge=1)
    charge_amount: Amount
    allowed_amount: Amount
    paid_amount: Amount
    contract_id: ContractId | None = Field(
        default=None, description="Payer contract covering this CPT category, if any"
    )
    expected_reimbursement: Amount | None = Field(
        default=None, description="charge × contracted rate, for JAB Audit to verify"
    )


class Remittance(BaseModel):
    """From the payer's 835 ERA."""

    check_number: str | None = None
    check_date: date | None = None
    carc_codes: list[str] = Field(default_factory=list)
    rarc_codes: list[str] = Field(default_factory=list)


class ClaimHandoff(BaseModel):
    """An adjudicated claim, with the validation context JAB Audit can't see on its own."""

    claim_id: ClaimId
    payer_id: PayerId
    service_date: date
    adjudicated_on: date
    total_charge: Amount
    total_allowed: Amount
    total_paid: Amount
    lines: list[HandoffLine] = Field(min_length=1)
    remittance: Remittance
    validation_status: ValidationStatus = Field(description="Status when the claim was submitted")
    risk_score: int = Field(ge=0, le=100)
    corrected_fields: list[str] = Field(
        default_factory=list, description="Fields changed by an AI Fix before submission"
    )


class HandoffBatch(BaseModel):
    batch_id: str = Field(description="Idempotency key: resending a batch is a no-op")
    sent_at: datetime
    claims: list[ClaimHandoff] = Field(min_length=1, max_length=500)


class HandoffAccepted(BaseModel):
    batch_id: str
    accepted: int = Field(ge=0)
    rejected: list[ClaimId] = Field(default_factory=list)


# --- 2. Underpayment findings (JAB Audit -> ClaustraRCM) ----------------------------


class VarianceReason(StrEnum):
    RATE_MISMATCH = "rate_mismatch"  # paid below the contracted rate
    OUTDATED_FEE_SCHEDULE = "outdated_fee_schedule"
    INCORRECT_BUNDLING = "incorrect_bundling"
    MODIFIER_REDUCTION = "modifier_reduction"
    UNITS_REDUCED = "units_reduced"
    OTHER = "other"


class UnderpaymentFinding(BaseModel):
    finding_id: FindingId
    claim_id: ClaimId
    line_id: LineId | None = Field(default=None, description="None for claim-level findings")
    contract_id: ContractId | None = None
    expected_amount: Amount
    paid_amount: Amount
    variance: SignedAmount = Field(description="expected − paid; positive means underpaid")
    reason: VarianceReason
    confidence: Ratio = Field(description="0–1: how sure JAB Audit is the variance is recoverable")
    explanation: str
    appeal_deadline: date | None = None


class FindingsBatch(BaseModel):
    """Webhook body. Signed with HMAC-SHA256 in the X-JAB-Signature header."""

    batch_id: str
    findings: list[UnderpaymentFinding] = Field(min_length=1)


# --- 3. Recovery status (JAB Audit -> ClaustraRCM) ------------------------------------


class RecoveryStatus(StrEnum):
    IDENTIFIED = "identified"
    APPEAL_SUBMITTED = "appeal_submitted"
    PAYER_REVIEW = "payer_review"
    RECOVERED = "recovered"
    PARTIALLY_RECOVERED = "partially_recovered"
    DENIED = "denied"
    WRITTEN_OFF = "written_off"


class RecoveryUpdate(BaseModel):
    finding_id: FindingId
    status: RecoveryStatus
    recovered_amount: Amount = Decimal("0.00")
    updated_at: datetime
    note: str | None = None


# --- 4. Rule suggestions (JAB Audit -> ClaustraRCM Rule Manager) ---------------------


class RuleSuggestion(BaseModel):
    """A recurring underpayment pattern, proposed as a pre-submission rule.

    Lands as a disabled draft in Rule Manager; a person reviews and enables it.
    """

    suggestion_id: str
    rule: RuleCreate
    evidence_finding_ids: list[FindingId] = Field(min_length=1)
    claims_affected: int = Field(ge=1)
    amount_at_stake: Amount


# --- Contract catalog served to the JAB Audit page ----------------------------------


class Direction(StrEnum):
    OUTBOUND = "outbound"  # ClaustraRCM calls JAB Audit
    INBOUND = "inbound"  # JAB Audit calls ClaustraRCM (webhook)


class ContractField(BaseModel):
    """One field of a payload, flattened for display: `claims[].lines[].cpt_code`."""

    path: str
    type: str
    required: bool
    description: str | None = None
    allowed_values: list[str] | None = None
    pattern: str | None = None


class ApiContract(BaseModel):
    id: str
    title: str
    direction: Direction
    method: str
    path: str
    purpose: str
    request_model: str
    request_fields: list[ContractField]
    request_schema: dict[str, Any]
    request_example: dict[str, Any]
    response_model: str | None = None
    response_schema: dict[str, Any] | None = None
    notes: list[str] = Field(default_factory=list)
