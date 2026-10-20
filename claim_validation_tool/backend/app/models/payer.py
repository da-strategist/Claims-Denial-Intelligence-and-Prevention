"""Payer (insurance company) model — mirrors dim_payers.csv."""

from enum import StrEnum

from pydantic import Field

from app.models.common import DomainModel, PayerId, Ratio, RecordStatus


class PayerType(StrEnum):
    MEDICARE = "Medicare"
    MEDICARE_ADVANTAGE = "Medicare Advantage"
    MEDICAID = "Medicaid"
    MEDICAID_MCO = "Medicaid MCO"
    COMMERCIAL = "Commercial"
    GOVERNMENT = "Government"
    WORKERS_COMP = "Workers Comp"
    SELF_PAY = "Self-Pay"


class Payer(DomainModel):
    payer_id: PayerId
    payer_name: str
    payer_type: PayerType
    market_share: Ratio
    denial_rate: Ratio
    avg_days_to_pay: int = Field(ge=0)
    pa_strictness: Ratio = Field(description="0-1 likelihood the payer enforces prior auth")
    policy_prefix: str
    status: RecordStatus
