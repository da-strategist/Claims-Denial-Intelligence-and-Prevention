from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

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


class ReviewPerson(BaseModel):
    patient_id: str
    first_name: str
    last_name: str
    birth_date: date | None = None  # unknown until a claim records it


class PatientToReview(ReviewPerson):
    """A patient first seen on a claim who may be someone already on the list."""

    possible_matches: list[ReviewPerson]


def _person(patient, repo, registrations) -> ReviewPerson:
    registration = registrations.get(patient, repo.get_payer(patient.primary_payer_id), repository_module._today())
    return ReviewPerson(
        patient_id=patient.patient_id,
        first_name=patient.first_name,
        last_name=patient.last_name,
        birth_date=registration.birth_date if registration else None,
    )


@router.get("/to-review", response_model=list[PatientToReview])
def patients_to_review(repo: Claims, registrations: Registrations) -> list[PatientToReview]:
    """Patients added from a claim who may be a duplicate, and who they may be."""
    result = []
    for patient_id, matches in repo.patients_to_review().items():
        patient = repo.get_patient(patient_id)
        if patient is None:
            continue
        others = [repo.get_patient(match) for match in matches]
        result.append(
            PatientToReview(
                **_person(patient, repo, registrations).model_dump(),
                possible_matches=[_person(other, repo, registrations) for other in others if other],
            )
        )
    return result


@router.post(
    "/{patient_id}/not-a-duplicate", status_code=204, dependencies=[require(Permission.CLAIMS_WRITE)]
)
def mark_not_a_duplicate(patient_id: PatientId, repo: Claims) -> None:
    """Someone has checked: this is a different person, so stop flagging them."""
    if not repo.clear_patient_review(patient_id):
        raise HTTPException(status_code=404, detail=f"{patient_id} isn't waiting for review")


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
    the patient's last claim, or generated sample details (`source` says which) in a
    sample organisation. 404 when nothing is on record yet."""
    patient = repo.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
    payer = repo.get_payer(patient.primary_payer_id)
    registration = registrations.get(patient, payer, repository_module._today())
    if registration is None:
        raise HTTPException(status_code=404, detail=f"Nothing on record for {patient_id} yet: enter their details")
    return registration
