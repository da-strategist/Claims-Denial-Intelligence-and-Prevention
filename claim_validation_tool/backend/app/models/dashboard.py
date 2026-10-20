"""Executive dashboard models: KPIs and chart series for /api/dashboard."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.common import DepartmentId, PayerId
from app.models.rule import ValidationStatus


class DashboardQuery(BaseModel):
    """Which claims the dashboard summarizes."""

    months: int | None = Field(
        default=None,
        ge=1,
        le=36,
        description="Trailing months of service dates, ending at the latest month in the data. "
        "Omit for all time.",
    )
    payer_id: PayerId | None = None
    department_id: DepartmentId | None = None


class KpiFormat(StrEnum):
    COUNT = "count"
    CURRENCY = "currency"
    PERCENT = "percent"  # a 0–1 ratio
    DAYS = "days"


class Kpi(BaseModel):
    key: str
    label: str
    value: float
    format: KpiFormat
    previous: float | None = Field(
        default=None, description="Same KPI over the preceding period of equal length"
    )
    higher_is_better: bool | None = Field(description="null for neutral measures such as volume")
    detail: str | None = None


class Period(BaseModel):
    start: date
    end: date


class MonthlyRevenue(BaseModel):
    month: str = Field(description="YYYY-MM of the service date")
    claims: int
    charges: float
    allowed: float
    paid: float
    denied: float = Field(description="Amount denied on this month's claims")


class DenialReason(BaseModel):
    category: str
    denials: int
    amount: float
    preventable: int


class AgingBucket(BaseModel):
    label: str = Field(description='Day range, e.g. "31–60"')
    min_days: int
    max_days: int | None
    claims: int
    charges: float


class StatusCount(BaseModel):
    status: ValidationStatus
    claims: int


class PayerSummary(BaseModel):
    payer_id: PayerId
    payer_name: str
    claims: int
    denial_rate: float
    avg_days_in_ar: float
    paid: float


class DraftSummary(BaseModel):
    """Claims entered but not yet submitted, to finish on New Claim."""

    claims: int = Field(ge=0)
    with_problems: int = Field(ge=0, description="Still have a rule error or warning")


class Dashboard(BaseModel):
    period: Period | None = Field(description="Service dates covered; null when no claims match")
    comparison_period: Period | None = None
    data_range: Period
    kpis: list[Kpi]
    revenue_trend: list[MonthlyRevenue]
    denial_reasons: list[DenialReason]
    ar_aging: list[AgingBucket]
    validation_status: list[StatusCount]
    payers: list[PayerSummary]
    drafts: DraftSummary = Field(
        description="Payer and department filters apply; the period doesn't (drafts are current work)"
    )
