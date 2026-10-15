from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.data import ClaimsRepository, get_repository
from app.models import Claim, ClaimDetail, ClaimQuery, Page
from app.models.common import ClaimId

router = APIRouter(prefix="/api/claims", tags=["claims"])


@router.get("", response_model=Page[Claim])
def list_claims(
    query: Annotated[ClaimQuery, Query()],
    repo: Annotated[ClaimsRepository, Depends(get_repository)],
) -> Page[Claim]:
    """List claims with search, filtering, sorting, and pagination."""
    return repo.list_claims(query)


@router.get("/{claim_id}", response_model=ClaimDetail)
def get_claim(
    claim_id: ClaimId,
    repo: Annotated[ClaimsRepository, Depends(get_repository)],
) -> ClaimDetail:
    """Single claim with its lines, denials, payer, and provider."""
    claim = repo.get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return claim
