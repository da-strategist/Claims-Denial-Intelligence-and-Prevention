"""Aggregates claims, denials, and validation results into the executive dashboard.

The period is anchored to the latest service month in the data (the synthetic data
ends before today), and KPIs are compared with the preceding period of equal length.
"""

from datetime import date

import pandas as pd

from app.models import (
    ADJUDICATED_STATUSES,
    AT_RISK_STATUSES,
    AgingBucket,
    ClaimStatus,
    Dashboard,
    DashboardQuery,
    DraftSummary,
    DenialReason,
    Kpi,
    KpiFormat,
    MonthlyRevenue,
    Payer,
    PayerSummary,
    Period,
    StatusCount,
    ValidationStatus,
)

# (label in days, min days, max days or None for open-ended)
AR_BUCKETS: list[tuple[str, int, int | None]] = [
    ("0–30", 0, 30),
    ("31–60", 31, 60),
    ("61–90", 61, 90),
    ("90+", 91, None),
]


def build_dashboard(
    query: DashboardQuery,
    claims: pd.DataFrame,
    denials: pd.DataFrame,
    statuses: pd.DataFrame,
    payers: dict[str, Payer],
) -> Dashboard:
    """`claims`/`denials` are the full repository frames; `statuses` comes from StatusSnapshot."""
    data_range = Period(
        start=date.fromisoformat(claims["service_date"].min()),
        end=date.fromisoformat(claims["service_date"].max()),
    )
    scoped = claims
    if query.payer_id is not None:
        scoped = scoped[scoped["payer_id"] == query.payer_id]
    if query.department_id is not None:
        scoped = scoped[scoped["department_id"] == query.department_id]

    period, comparison = _periods(query.months, data_range)
    current = _in_period(scoped, period)
    previous = _in_period(scoped, comparison) if comparison else None
    if previous is not None and previous.empty:
        previous, comparison = None, None

    current_denials = denials[denials["claim_id"].isin(current["claim_id"])]
    previous_denials = (
        denials[denials["claim_id"].isin(previous["claim_id"])] if previous is not None else None
    )
    current_status = statuses["status"].reindex(current["claim_id"])

    return Dashboard(
        period=_actual_period(current) if period is None else period,
        comparison_period=comparison,
        data_range=data_range,
        kpis=_kpis(
            current,
            current_denials,
            current_status,
            previous,
            previous_denials,
            statuses["status"].reindex(previous["claim_id"]) if previous is not None else None,
        ),
        revenue_trend=_revenue_trend(current, current_denials),
        denial_reasons=_denial_reasons(current_denials),
        ar_aging=_ar_aging(current),
        validation_status=[
            StatusCount(status=status, claims=int((current_status == status.value).sum()))
            for status in ValidationStatus
        ],
        payers=_payers(current, payers),
        drafts=_drafts(scoped, statuses),
    )


def _drafts(scoped: pd.DataFrame, statuses: pd.DataFrame) -> DraftSummary:
    """Unsubmitted claims under the payer/department filters, whatever their service date."""
    drafts = scoped[scoped["status"] == ClaimStatus.DRAFT]
    status = statuses["status"].reindex(drafts["claim_id"])
    return DraftSummary(
        claims=len(drafts),
        with_problems=int((status != ValidationStatus.PASS.value).sum()),
    )


# --- Periods --------------------------------------------------------------------


def _periods(months: int | None, data_range: Period) -> tuple[Period | None, Period | None]:
    """The selected period and the one before it, or (None, None) for all time.

    The window counts back from the latest service date in the data. That suits the
    synthetic sample (it ends in December 2025); before going live on real claims, count
    back from today instead. See PHASES.md, "Before going live".
    """
    if months is None:
        return None, None
    last = pd.Period(data_range.end, freq="M")
    first = last - (months - 1)
    period = Period(start=first.start_time.date(), end=last.end_time.date())
    before_last = first - 1
    comparison = Period(
        start=(before_last - (months - 1)).start_time.date(), end=before_last.end_time.date()
    )
    return period, comparison


def _in_period(claims: pd.DataFrame, period: Period | None) -> pd.DataFrame:
    if period is None:
        return claims
    dates = claims["service_date"]
    return claims[(dates >= period.start.isoformat()) & (dates <= period.end.isoformat())]


def _actual_period(claims: pd.DataFrame) -> Period | None:
    if claims.empty:
        return None
    return Period(
        start=date.fromisoformat(claims["service_date"].min()),
        end=date.fromisoformat(claims["service_date"].max()),
    )


# --- KPIs -----------------------------------------------------------------------


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _submitted(claims: pd.DataFrame) -> pd.DataFrame:
    """Claims sent to a payer: drafts aren't in accounts receivable yet."""
    return claims[claims["status"] != ClaimStatus.DRAFT]


def _measures(claims: pd.DataFrame, denials: pd.DataFrame, status: pd.Series) -> dict[str, float]:
    denied = claims["status"] == ClaimStatus.DENIED
    adjudicated = claims["status"].isin(ADJUDICATED_STATUSES)
    submitted = _submitted(claims)
    # Needs attention counts submitted claims, like the Claims queue; drafts are listed apart
    submitted_status = status[(claims["status"] != ClaimStatus.DRAFT).to_numpy()]
    return {
        "claims": len(claims),
        "charges": float(claims["total_charge"].sum()),
        "paid": float(claims["total_paid"].sum()),
        "drafts": int((claims["status"] == ClaimStatus.DRAFT).sum()),
        "pending": int((claims["status"] == ClaimStatus.PENDING).sum()),
        "overdue": int(claims["is_overdue"].sum()),
        "denial_rate": _ratio(denied.sum(), adjudicated.sum()),
        "denied_claims": int(denied.sum()),
        "denied_amount": float(denials["denial_amount"].sum()),
        "preventable_share": _ratio(denials["is_preventable"].sum(), len(denials)),
        "clean_claim_rate": _ratio(claims["is_clean_claim"].sum(), len(claims)),
        "avg_days_in_ar": float(submitted["days_in_ar"].mean()) if len(submitted) else 0.0,
        "over_60_days": int((submitted["days_in_ar"] > 60).sum()),
        "net_collection_rate": _ratio(claims["total_paid"].sum(), claims["total_allowed"].sum()),
        "at_risk": int(submitted_status.isin(AT_RISK_STATUSES).sum()),
        "aifix": int((submitted_status == ValidationStatus.AI_FIX.value).sum()),
    }


def _kpis(
    claims: pd.DataFrame,
    denials: pd.DataFrame,
    status: pd.Series,
    previous_claims: pd.DataFrame | None,
    previous_denials: pd.DataFrame | None,
    previous_status: pd.Series | None,
) -> list[Kpi]:
    now = _measures(claims, denials, status)
    before = (
        _measures(previous_claims, previous_denials, previous_status)
        if previous_claims is not None
        else {}
    )

    def kpi(
        key: str, label: str, fmt: KpiFormat, higher_is_better: bool | None, detail: str
    ) -> Kpi:
        return Kpi(
            key=key,
            label=label,
            value=now[key],
            format=fmt,
            previous=before.get(key),
            higher_is_better=higher_is_better,
            detail=detail,
        )

    return [
        kpi("claims", "Total Claims", KpiFormat.COUNT, None, _claims_detail(now)),
        kpi(
            "denial_rate",
            "Denial Rate",
            KpiFormat.PERCENT,
            False,
            f"{now['denied_claims']:,} denied · {_money(now['denied_amount'])} · "
            f"{now['preventable_share']:.0%} preventable",
        ),
        kpi(
            "clean_claim_rate",
            "Clean Claim Rate",
            KpiFormat.PERCENT,
            True,
            "Accepted on first submission",
        ),
        kpi(
            "avg_days_in_ar",
            "Avg Days in AR",
            KpiFormat.DAYS,
            False,
            f"{now['over_60_days']:,} claims over 60 days"
            + (f" · {now['overdue']:,} pending overdue" if now["overdue"] else ""),
        ),
        kpi(
            "net_collection_rate",
            "Net Collection Rate",
            KpiFormat.PERCENT,
            True,
            f"{_money(now['paid'])} collected of allowed",
        ),
        kpi(
            "at_risk",
            "At-Risk Claims",
            KpiFormat.COUNT,
            False,
            f"{now['aifix']:,} of them have an AI fix ready" if now["aifix"] else "",
        ),
    ]


def _claims_detail(now: dict[str, float]) -> str:
    parts = [f"{_money(now['charges'])} billed"]
    if now["drafts"]:
        parts.append(f"{now['drafts']:,} draft")
    if now["pending"]:
        parts.append(f"{now['pending']:,} pending")
    return " · ".join(parts)


def _money(amount: float) -> str:
    for size, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(amount) >= size:
            return f"${amount / size:.1f}{suffix}"
    return f"${amount:,.0f}"


# --- Charts ---------------------------------------------------------------------


def _revenue_trend(claims: pd.DataFrame, denials: pd.DataFrame) -> list[MonthlyRevenue]:
    month = claims["service_date"].str[:7]
    monthly = claims.groupby(month).agg(
        claims=("claim_id", "size"),
        charges=("total_charge", "sum"),
        allowed=("total_allowed", "sum"),
        paid=("total_paid", "sum"),
    )
    denial_month = denials["claim_id"].map(pd.Series(month.values, index=claims["claim_id"]))
    denied = denials["denial_amount"].groupby(denial_month).sum()
    monthly["denied"] = denied.reindex(monthly.index, fill_value=0.0)
    return [
        MonthlyRevenue(month=str(month_key), **row)
        for month_key, row in monthly.sort_index().to_dict("index").items()
    ]


def _denial_reasons(denials: pd.DataFrame) -> list[DenialReason]:
    grouped = denials.groupby("root_cause_category").agg(
        denials=("denial_id", "size"),
        amount=("denial_amount", "sum"),
        preventable=("is_preventable", "sum"),
    )
    return [
        DenialReason(category=str(category), **row)
        for category, row in grouped.sort_values(["denials", "amount"], ascending=False)
        .to_dict("index")
        .items()
    ]


def _ar_aging(claims: pd.DataFrame) -> list[AgingBucket]:
    claims = _submitted(claims)
    days = claims["days_in_ar"]
    buckets = []
    for label, low, high in AR_BUCKETS:
        mask = days >= low if high is None else days.between(low, high)
        buckets.append(
            AgingBucket(
                label=label,
                min_days=low,
                max_days=high,
                claims=int(mask.sum()),
                charges=float(claims.loc[mask, "total_charge"].sum()),
            )
        )
    return buckets


def _payers(claims: pd.DataFrame, payers: dict[str, Payer]) -> list[PayerSummary]:
    # Rates only over claims they apply to (NaN rows are skipped by mean)
    adjudicated = claims["status"].isin(ADJUDICATED_STATUSES)
    submitted = claims["status"] != ClaimStatus.DRAFT
    grouped = (
        claims.assign(
            denied=(claims["status"] == ClaimStatus.DENIED).astype(float).where(adjudicated),
            ar_days=claims["days_in_ar"].where(submitted),
        )
        .groupby("payer_id")
        .agg(
            claims=("claim_id", "size"),
            denial_rate=("denied", "mean"),
            avg_days_in_ar=("ar_days", "mean"),
            paid=("total_paid", "sum"),
        )
        .fillna(0.0)
    )
    return [
        PayerSummary(
            payer_id=payer_id,
            payer_name=payers[payer_id].payer_name if payer_id in payers else payer_id,
            **row,
        )
        for payer_id, row in grouped.sort_values("claims", ascending=False).to_dict("index").items()
    ]
