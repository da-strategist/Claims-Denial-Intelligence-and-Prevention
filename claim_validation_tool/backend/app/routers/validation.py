from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.data import ClaimsRepository, RuleRepository, get_repository, get_rule_repository
from app.models import ClaimValidation, Rule, ValidateRequest
from app.models.common import ClaimId
from app.services import validation_engine

router = APIRouter(prefix="/api/validate", tags=["validation"])

Claims = Annotated[ClaimsRepository, Depends(get_repository)]
Rules = Annotated[RuleRepository, Depends(get_rule_repository)]


@router.post("", response_model=list[ClaimValidation])
def validate_claims(request: ValidateRequest, claims: Claims, rules: Rules) -> list[ClaimValidation]:
    """Validate up to 200 claims against the enabled rules (or a chosen subset)."""
    missing = claims.missing_claim_ids(request.claim_ids)
    if missing:
        raise HTTPException(status_code=404, detail=f"Claims not found: {', '.join(missing)}")
    return validation_engine.validate_claims(
        claims.claims_frame(list(dict.fromkeys(request.claim_ids))),
        _select_rules(rules, request.rule_ids),
    )


@router.get("/{claim_id}", response_model=ClaimValidation)
def validate_claim(claim_id: ClaimId, claims: Claims, rules: Rules) -> ClaimValidation:
    """Validate a single claim against all enabled rules."""
    if claims.missing_claim_ids([claim_id]):
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return validation_engine.validate_claims(claims.claims_frame([claim_id]), rules.list())[0]


def _select_rules(rules: RuleRepository, rule_ids: list[str] | None) -> list[Rule]:
    if rule_ids is None:
        return rules.list()
    selected = [rules.get(rule_id) for rule_id in rule_ids]
    missing = [rule_id for rule_id, rule in zip(rule_ids, selected) if rule is None]
    if missing:
        raise HTTPException(status_code=404, detail=f"Rules not found: {', '.join(missing)}")
    return selected
