from typing import Annotated

from fastapi import APIRouter, Depends

from app.data import ClaimsRepository, get_repository
from app.models import Department, Permission
from app.services.auth import require

router = APIRouter(
    prefix="/api/departments", tags=["departments"], dependencies=[require(Permission.CLAIMS_READ)]
)


@router.get("", response_model=list[Department])
def list_departments(
    repo: Annotated[ClaimsRepository, Depends(get_repository)],
) -> list[Department]:
    return repo.list_departments()
