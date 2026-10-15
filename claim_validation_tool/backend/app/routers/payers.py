from typing import Annotated

from fastapi import APIRouter, Depends

from app.data import ClaimsRepository, get_repository
from app.models import Payer

router = APIRouter(prefix="/api/payers", tags=["payers"])


@router.get("", response_model=list[Payer])
def list_payers(
    repo: Annotated[ClaimsRepository, Depends(get_repository)],
) -> list[Payer]:
    return repo.list_payers()
