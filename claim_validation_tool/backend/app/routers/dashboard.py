from typing import Annotated

from fastapi import APIRouter, Query

from app.models import Dashboard, DashboardQuery, Permission
from app.services.auth import require
from app.services.dashboard import build_dashboard
from app.data import repository
from app.data.orgs import get_org_registry
from app.services.org_context import OrgClaims, OrgId, OrgRules, OrgSnapshot

router = APIRouter(
    prefix="/api/dashboard", tags=["dashboard"], dependencies=[require(Permission.CLAIMS_READ)]
)


@router.get("", response_model=Dashboard)
def get_dashboard(
    query: Annotated[DashboardQuery, Query()],
    claims: OrgClaims,
    rules: OrgRules,
    snapshot: OrgSnapshot,
    org_id: OrgId,
) -> Dashboard:
    """KPIs and chart data for the executive dashboard. "Last N months" ends this month for
    a real organisation, and with the latest claim in a sample one."""
    org = get_org_registry().get(org_id)
    return build_dashboard(
        query,
        claims.claims_frame(),
        claims.denials_frame(),
        snapshot.get(claims, rules.list()),
        {payer.payer_id: payer for payer in claims.list_payers()},
        today=None if org and org.sample_data else repository._today(),
    )
