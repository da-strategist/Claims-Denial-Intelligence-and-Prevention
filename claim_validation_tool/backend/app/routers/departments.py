from typing import Annotated

from fastapi import APIRouter, Depends

from app.data import ClaimsRepository, get_repository
from app.models import Department

router = APIRouter(prefix="/api/departments", tags=["departments"])


@router.get("", response_model=list[Department])
def list_departments(
    repo: Annotated[ClaimsRepository, Depends(get_repository)],
) -> list[Department]:
    return repo.list_departments()
