from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.data import ClaimsRepository, RuleRepository, get_repository, get_rule_repository
from app.models import Dashboard, DashboardQuery
from app.services.dashboard import build_dashboard
from app.services.status_snapshot import StatusSnapshot, get_status_snapshot

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=Dashboard)
def get_dashboard(
    query: Annotated[DashboardQuery, Query()],
    claims: Annotated[ClaimsRepository, Depends(get_repository)],
    rules: Annotated[RuleRepository, Depends(get_rule_repository)],
    snapshot: Annotated[StatusSnapshot, Depends(get_status_snapshot)],
) -> Dashboard:
    """KPIs and chart data for the executive dashboard."""
    return build_dashboard(
        query,
        claims.claims_frame(),
        claims.denials_frame(),
        snapshot.get(claims, rules.list()),
        {payer.payer_id: payer for payer in claims.list_payers()},
    )
