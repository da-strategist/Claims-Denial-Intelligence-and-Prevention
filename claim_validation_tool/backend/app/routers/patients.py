from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.data import ClaimsRepository, get_repository
from app.models import Page, PatientQuery, PatientSummary
from app.models.common import PatientId

router = APIRouter(prefix="/api/patients", tags=["patients"])

Claims = Annotated[ClaimsRepository, Depends(get_repository)]


@router.get("", response_model=Page[PatientSummary])
def list_patients(query: Annotated[PatientQuery, Query()], repo: Claims) -> Page[PatientSummary]:
    """Search registered patients by ID or name."""
    return repo.list_patients(query)


@router.get("/{patient_id}", response_model=PatientSummary)
def get_patient(patient_id: PatientId, repo: Claims) -> PatientSummary:
    patient = repo.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
    return patient
