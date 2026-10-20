from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.data import repository as repository_module
from app.models import Page, PatientQuery, PatientRegistration, PatientSummary, Permission
from app.models.common import PatientId
from app.services.auth import require
from app.services.org_context import OrgClaims, OrgRegistrations

router = APIRouter(
    prefix="/api/patients", tags=["patients"], dependencies=[require(Permission.PATIENTS_READ)]
)

Claims = OrgClaims
Registrations = OrgRegistrations


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


@router.get("/{patient_id}/registration", response_model=PatientRegistration)
def get_registration(
    patient_id: PatientId, repo: Claims, registrations: Registrations
) -> PatientRegistration:
    """Date of birth, address, and policies to fill a new claim with: what was entered on
    the patient's last claim, or generated sample details (`source` says which)."""
    patient = repo.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
    payer = repo.get_payer(patient.primary_payer_id)
    return registrations.get(patient, payer, repository_module._today())
