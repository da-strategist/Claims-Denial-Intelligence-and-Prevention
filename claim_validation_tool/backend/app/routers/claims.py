from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.data import (
    ClaimsRepository,
    ReferenceData,
    RuleRepository,
    get_reference_data,
    get_repository,
    get_rule_repository,
)
from app.models import (
    Claim,
    ClaimCreate,
    ClaimCreated,
    ClaimDetail,
    ClaimQuery,
    ClaimStatus,
    Page,
    RecordStatus,
    ValidationStatus,
)
from app.models.common import ClaimId
from app.services import validation_engine

router = APIRouter(prefix="/api/claims", tags=["claims"])

Claims = Annotated[ClaimsRepository, Depends(get_repository)]
Rules = Annotated[RuleRepository, Depends(get_rule_repository)]

Reference = Annotated[ReferenceData, Depends(get_reference_data)]


@router.get("", response_model=Page[Claim])
def list_claims(query: Annotated[ClaimQuery, Query()], repo: Claims) -> Page[Claim]:
    """List claims with search, filtering, sorting, and pagination."""
    return repo.list_claims(query)


@router.post("", response_model=ClaimCreated, status_code=status.HTTP_201_CREATED)
def create_claim(
    body: ClaimCreate, repo: Claims, rules: Rules, reference: Reference
) -> ClaimCreated:
    """Enter a Draft claim for a registered patient and validate it.

    The department comes from the provider; each line's category (and, if omitted, its
    charge) from the CPT code set. Kept in memory until the server restarts.
    """
    patient = repo.get_patient(body.patient_id)
    if patient is None or patient.status != RecordStatus.ACTIVE:
        raise HTTPException(
            status_code=422, detail=f"Patient {body.patient_id} is not a registered patient"
        )
    for payer_id in (body.payer_id, *body.other_payer_ids):
        if repo.get_payer(payer_id) is None:
            raise HTTPException(status_code=422, detail=f"Unknown payer {payer_id}")
    provider = repo.get_provider(body.provider_id)
    if provider is None or provider.status != RecordStatus.ACTIVE:
        raise HTTPException(
            status_code=422, detail=f"Provider {body.provider_id} is not an active provider"
        )
    if repo.get_facility(body.facility_id) is None:
        raise HTTPException(status_code=422, detail=f"Unknown facility {body.facility_id}")

    lines = []
    for number, line in enumerate(body.lines, start=1):
        cpt = reference.cpt.get(line.cpt_code)
        if cpt is None:
            raise HTTPException(
                status_code=422, detail=f"Line {number}: unknown CPT code {line.cpt_code}"
            )
        charge = (
            line.charge_amount
            if line.charge_amount is not None
            else round(float(cpt["standard_charge"]) * line.units, 2)
        )
        lines.append(
            {
                "cpt_code": line.cpt_code,
                "cpt_category": cpt["category"],
                "modifier": line.modifier,
                "units": line.units,
                "charge_amount": charge,
                "icd10_pointer": line.icd10_pointer,
            }
        )

    claims = repo.claims_frame()
    header = body.model_dump(mode="json", exclude={"diagnoses", "lines"})
    fields = {
        **header,
        "claim_id": _next_id(claims["claim_id"], "CLM", 7),
        "department_id": provider.department_id,
        "primary_icd10": body.diagnoses[0],
        "additional_icd10": body.diagnoses[1:],
        "total_charge": round(sum(line["charge_amount"] for line in lines), 2),
        "status": ClaimStatus.DRAFT.value,
        "total_allowed": 0.0,
        "total_paid": 0.0,
        "patient_responsibility": 0.0,
        "days_in_ar": 0,
        # Nothing is known to be wrong with a new claim; rules and AI Fix flag real problems
        "is_clean_claim": True,
    }
    try:
        claim = repo.add_claim(fields, lines)
    except ValueError as err:  # another request took the same ID first
        raise HTTPException(status_code=409, detail=str(err)) from err
    validation = validation_engine.validate_claims(
        repo.claims_frame([claim.claim_id]), rules.list()
    )[0]
    return ClaimCreated(claim=claim, validation=validation)


@router.post("/{claim_id}/submit", response_model=ClaimCreated)
def submit_claim(claim_id: ClaimId, repo: Claims, rules: Rules) -> ClaimCreated:
    """Mark a Draft as submitted to the payer today. Refused while rule errors remain."""
    if repo.missing_claim_ids([claim_id]):
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    validation = validation_engine.validate_claims(repo.claims_frame([claim_id]), rules.list())[0]
    if validation.status in (ValidationStatus.ERROR, ValidationStatus.AI_FIX):
        raise HTTPException(
            status_code=422, detail="Resolve the rule errors before submitting this claim"
        )
    try:
        claim = repo.submit_claim(claim_id)
    except ValueError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err
    validation = validation_engine.validate_claims(repo.claims_frame([claim_id]), rules.list())[0]
    return ClaimCreated(claim=claim, validation=validation)


@router.get("/{claim_id}", response_model=ClaimDetail)
def get_claim(claim_id: ClaimId, repo: Claims) -> ClaimDetail:
    """Single claim with its lines, denials, payer, and provider."""
    claim = repo.get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return claim


def _next_id(ids: pd.Series, prefix: str, digits: int) -> str:
    """One past the highest existing ID: CLM0120000 -> CLM0120001."""
    highest = ids.str.removeprefix(prefix).astype("int64").max() if len(ids) else 0
    return f"{prefix}{int(highest) + 1:0{digits}d}"
