"""Hospital workspace: staff (hospital admins), patient records, and
policies that patients shared with the hospital. Everything is limited to the
signed-in user's own hospital; other hospitals' records are "not found"."""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import Path as PathParam
from pydantic import BaseModel, Field

from ..audit import audit_document, audit_patient, audit_target
from ..auth.access import Access
from ..auth.sessions import Permission, require, sessions
from ..auth.users import Role, User, user_store
from ..models.common import DOCUMENT_ID_PATTERN
from ..services import records, registry

router = APIRouter(prefix="/api/hospital", tags=["hospital"])

_staff_admin = require(Permission.MANAGE_STAFF)
_patients = require(Permission.MANAGE_PATIENTS)
UsernameParam = PathParam(min_length=3, max_length=254)
# One Path() object per parameter name: FastAPI binds a shared one to the first name it sees
PatientIdParam = PathParam(pattern=DOCUMENT_ID_PATTERN)
ShareIdParam = PathParam(pattern=DOCUMENT_ID_PATTERN)


# ── Staff (hospital admins) ──────────────────────────────────────────

class NewStaff(BaseModel):
    username: str = Field(min_length=3, max_length=254)
    role: Role = Role.HOSPITAL_STAFF


class StaffChanges(BaseModel):
    disabled: bool | None = None


def _own_staff_or_404(admin: User, username: str) -> User:
    user = user_store.get(username)
    if user is None or user.org_id != admin.org_id:
        raise HTTPException(404, "User not found")
    return user


@router.get("/staff")
async def list_staff(admin: User = Depends(_staff_admin)) -> list[dict]:
    return [u.public() for u in user_store.all() if u.org_id == admin.org_id]


@router.post("/staff")
async def add_staff(body: NewStaff, request: Request, admin: User = Depends(_staff_admin)) -> dict:
    """Add a staff member to this hospital (temporary password returned once)."""
    if body.role not in (Role.HOSPITAL_STAFF, Role.HOSPITAL_ADMIN):
        raise HTTPException(400, "Hospital accounts are staff or hospital admins")
    username = body.username.strip().lower()
    audit_target(request, username)
    temporary = secrets.token_urlsafe(12)
    try:
        user = user_store.create(username, temporary, body.role, org_id=admin.org_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {**user.public(), "temporary_password": temporary}


@router.patch("/staff/{username}")
async def update_staff(body: StaffChanges, username: str = UsernameParam,
                       admin: User = Depends(_staff_admin)) -> dict:
    user = _own_staff_or_404(admin, username)
    if body.disabled is None:
        return user.public()
    if user.username == admin.username and body.disabled:
        raise HTTPException(400, "You cannot disable your own account")
    updated = user_store.update(user.username, disabled=body.disabled)
    if updated.disabled:
        sessions.end_all_for(updated.username)
    return updated.public()


@router.post("/staff/{username}/reset-password")
async def reset_staff_password(username: str = UsernameParam,
                               admin: User = Depends(_staff_admin)) -> dict:
    user = _own_staff_or_404(admin, username)
    temporary = secrets.token_urlsafe(12)
    user_store.update(user.username, password=temporary, must_change_password=True)
    sessions.end_all_for(user.username)
    return {"username": user.username, "temporary_password": temporary}


# ── Patient records ──────────────────────────────────────────────────

class NewPatient(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    reference: str = Field("", max_length=50)
    date_of_birth: str = Field("", pattern=r"^(\d{4}-\d{2}-\d{2})?$")


def _patient_view(access: Access, patient: records.Patient, entries: list[dict]) -> dict:
    doc_ids = access.patient_document_ids(entries, patient.patient_id)
    return {
        "patient_id": patient.patient_id, "name": patient.name, "reference": patient.reference,
        "date_of_birth": patient.date_of_birth, "created_at": patient.created_at,
        "documents": [
            {**{k: e.get(k) for k in ("document_id", "filename", "plan_name", "insurer_name",
                                      "status", "page_count")},
             "shared_by": e.get("owner")}
            for e in entries if e["document_id"] in doc_ids
        ],
    }


@router.get("/patients")
async def list_patients(user: User = Depends(_patients)) -> list[dict]:
    access, entries = Access(user), registry.load()
    mine = [p for p in records.patients.all() if p.org_id == user.org_id]
    return [_patient_view(access, p, entries) for p in sorted(mine, key=lambda p: p.name.lower())]


@router.post("/patients")
async def create_patient(body: NewPatient, request: Request,
                         user: User = Depends(_patients)) -> dict:
    patient = records.patients.add(records.Patient(
        records.new_id(), user.org_id, body.name.strip(), body.reference.strip(),
        body.date_of_birth, created_by=user.username))
    audit_patient(request, patient.patient_id)
    return _patient_view(Access(user), patient, registry.load())


@router.get("/patients/{patient_id}")
async def get_patient(patient_id: str = PatientIdParam, user: User = Depends(_patients)) -> dict:
    access = Access(user)
    return _patient_view(access, access.patient_or_404(patient_id), registry.load())


# ── Policies shared with this hospital ───────────────────────────────

class FileShare(BaseModel):
    patient_id: str | None = Field(None, pattern=DOCUMENT_ID_PATTERN)


@router.get("/shared")
async def list_shared(user: User = Depends(_patients)) -> list[dict]:
    """Policies individuals shared with this hospital."""
    entries = {e["document_id"]: e for e in registry.load()}
    out = []
    for share in records.shares.all():
        if share.org_id != user.org_id or share.document_id not in entries:
            continue
        e = entries[share.document_id]
        out.append({"share_id": share.share_id, "document_id": share.document_id,
                    "filename": e.get("filename"), "plan_name": e.get("plan_name"),
                    "shared_by": share.shared_by, "patient_id": share.patient_id,
                    "created_at": share.created_at})
    return out


@router.patch("/shared/{share_id}")
async def file_shared(body: FileShare, request: Request, share_id: str = ShareIdParam,
                      user: User = Depends(_patients)) -> dict:
    """File a shared policy under one of this hospital's patients (or unfile)."""
    share = records.shares.get(share_id)
    if share is None or share.org_id != user.org_id:
        raise HTTPException(404, "Share not found")
    if body.patient_id:
        Access(user).patient_or_404(body.patient_id)
    audit_document(request, share.document_id)
    audit_patient(request, body.patient_id)
    records.shares.update(share_id, patient_id=body.patient_id)
    return {"share_id": share_id, "patient_id": body.patient_id}
