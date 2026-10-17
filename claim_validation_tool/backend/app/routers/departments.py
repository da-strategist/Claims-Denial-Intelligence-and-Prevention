
from fastapi import APIRouter

from app.models import Department, Permission
from app.services.auth import require
from app.services.org_context import OrgClaims

router = APIRouter(
    prefix="/api/departments", tags=["departments"], dependencies=[require(Permission.CLAIMS_READ)]
)


@router.get("", response_model=list[Department])
def list_departments(
    repo: OrgClaims,
) -> list[Department]:
    return repo.list_departments()
