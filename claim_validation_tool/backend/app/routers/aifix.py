from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.models import ApplyFixRequest, ApplyFixResult, ClaimFixes, Permission, User
from app.models.common import ClaimId
from app.services import aifix
from app.services.aifix import FixSuggester, SuggestionError, get_suggester
from app.services.auth import require
from app.services.org_context import OrgClaims, OrgCorrections, OrgReference, OrgRules

router = APIRouter(prefix="/api/aifix", tags=["aifix"], dependencies=[require(Permission.CLAIMS_READ)])

WRITE = require(Permission.CLAIMS_WRITE)


class Deps:
    """The stores and services every AI Fix route needs."""

    def __init__(
        self,
        claims: OrgClaims,
        rules: OrgRules,
        corrections: OrgCorrections,
        reference: OrgReference,
        suggester: Annotated[FixSuggester, Depends(get_suggester)],
    ) -> None:
        self.args = (claims, rules, corrections, reference, suggester)


AiFixDeps = Annotated[Deps, Depends()]


@router.get("/{claim_id}", response_model=ClaimFixes)
def get_fixes(claim_id: ClaimId, deps: AiFixDeps) -> ClaimFixes:
    """Validation result, fix suggestions with citations, and applied corrections for a claim."""
    fixes = aifix.claim_fixes(claim_id, *deps.args)
    if fixes is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return fixes


@router.post("/{claim_id}/apply", response_model=ApplyFixResult)
def apply_fix(
    claim_id: ClaimId,
    request: ApplyFixRequest,
    deps: AiFixDeps,
    user: Annotated[User, WRITE],
) -> ApplyFixResult:
    """Apply an accepted suggestion to the claim and re-validate it."""
    try:
        before, applied, after = aifix.apply_fix(
            claim_id, request.suggestion_id, request.values, *deps.args, applied_by=user.username
        )
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from None
    except SuggestionError as err:
        raise HTTPException(status_code=422, detail=str(err)) from None
    return ApplyFixResult(claim_id=claim_id, applied=applied, before=before, after=after)


@router.delete("/{claim_id}/corrections", response_model=ClaimFixes, dependencies=[WRITE])
def undo_corrections(claim_id: ClaimId, deps: AiFixDeps) -> ClaimFixes:
    """Undo every correction on the claim, restoring its source values."""
    fixes = aifix.undo_corrections(claim_id, *deps.args)
    if fixes is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return fixes
