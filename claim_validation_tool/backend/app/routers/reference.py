"""Lists the claim-entry form picks from: providers, facilities, and code sets."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.data import ClaimsRepository, ReferenceData, get_reference_data, get_repository
from app.models import DiagnosisCode, Facility, Permission, ProcedureCode, Provider
from app.services.auth import require

router = APIRouter(prefix="/api", tags=["reference"], dependencies=[require(Permission.CLAIMS_READ)])

Claims = Annotated[ClaimsRepository, Depends(get_repository)]
Reference = Annotated[ReferenceData, Depends(get_reference_data)]


@router.get("/providers", response_model=list[Provider])
def list_providers(repo: Claims) -> list[Provider]:
    return repo.list_providers()


@router.get("/facilities", response_model=list[Facility])
def list_facilities(repo: Claims) -> list[Facility]:
    return repo.list_facilities()


@router.get("/codes/procedures", response_model=list[ProcedureCode])
def list_procedure_codes(reference: Reference) -> list[ProcedureCode]:
    """CPT codes with their standard charge."""
    return [ProcedureCode.model_validate(row) for row in reference.cpt.values()]


@router.get("/codes/diagnoses", response_model=list[DiagnosisCode])
def list_diagnosis_codes(reference: Reference) -> list[DiagnosisCode]:
    """Common ICD-10 codes, offered as suggestions (any valid ICD-10 code is accepted)."""
    return [DiagnosisCode.model_validate(row) for row in reference.icd10.values()]
