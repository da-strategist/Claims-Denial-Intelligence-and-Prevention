
from fastapi import APIRouter

from app.models import Payer, Permission
from app.services.auth import require
from app.services.org_context import OrgClaims

router = APIRouter(
    prefix="/api/payers", tags=["payers"], dependencies=[require(Permission.CLAIMS_READ)]
)


@router.get("", response_model=list[Payer])
def list_payers(
    repo: OrgClaims,
) -> list[Payer]:
    return repo.list_payers()
