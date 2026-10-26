"""Hospital workspace: staff (hospital admins), patient records, and
policies that patients shared with the hospital. Everything is limited to the
signed-in user's own hospital; other hospitals' records are "not found"."""

import secrets
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi import Path as PathParam
from pydantic import BaseModel, Field

from .. import audit
from ..audit import audit_document, audit_patient, audit_target
from ..auth.access import Access
from ..auth.sessions import Permission, require, sessions
from ..auth.users import Role, User, user_store
from ..models.common import DOCUMENT_ID_PATTERN
from ..services import documents, records, registry

router = APIRouter(prefix="/api/hospital", tags=["hospital"])

_staff_admin = require(Permission.MANAGE_STAFF)
_patients = require(Permission.MANAGE_PATIENTS)
UsernameParam = PathParam(min_length=3, max_length=254)
# One Path() object per parameter name: FastAPI binds a shared one to the first name it sees
PatientIdParam = PathParam(pattern=DOCUMENT_ID_PATTERN)
ShareIdParam = PathParam(pattern=DOCUMENT_ID_PATTERN)
ChecklistIdParam = PathParam(pattern=DOCUMENT_ID_PATTERN)
ConnectionIdParam = PathParam(pattern=DOCUMENT_ID_PATTERN)
ENDING_SOON_DAYS = 30
NEW_SHARE_DAYS = 7


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
        raise HTTPException(400, "Provider accounts are staff or provider admins")
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


class Merge(BaseModel):
    into_patient_id: str = Field(pattern=DOCUMENT_ID_PATTERN)


class PatientChanges(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    reference: str | None = Field(None, max_length=50)
    date_of_birth: str | None = Field(None, pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    archived: bool | None = None


def _coverage_status(entry: dict, today: str) -> str:
    """active / ended / upcoming / unknown, from the policy's stated dates."""
    start, end = entry.get("effective_date") or "", entry.get("expiration_date") or ""
    if end and end < today:
        return "ended"
    if start and start > today:
        return "upcoming"
    return "active" if (start or end) else "unknown"


def _patient_view(access: Access, patient: records.Patient, entries: list[dict]) -> dict:
    doc_ids = access.patient_document_ids(entries, patient.patient_id)
    today = date.today().isoformat()
    return {
        "patient_id": patient.patient_id, "name": patient.name, "reference": patient.reference,
        "date_of_birth": patient.date_of_birth, "archived": patient.archived,
        "linked_username": patient.linked_username, "created_at": patient.created_at,
        "documents": [
            {**{k: e.get(k) for k in ("document_id", "filename", "display_name", "plan_name",
                                      "insurer_name", "plan_id", "effective_date",
                                      "expiration_date", "status", "page_count")},
             "coverage_status": _coverage_status(e, today),
             "shared_by": e.get("owner")}
            for e in entries if e["document_id"] in doc_ids
        ],
    }


@router.get("/patients")
async def list_patients(include_archived: bool = Query(False),
                        user: User = Depends(_patients)) -> list[dict]:
    access, entries = Access(user), registry.load()
    mine = [p for p in records.patients.all()
            if p.org_id == user.org_id and (include_archived or not p.archived)]
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


@router.patch("/patients/{patient_id}")
async def update_patient(body: PatientChanges, patient_id: str = PatientIdParam,
                         user: User = Depends(_patients)) -> dict:
    """Correct details, or archive / restore (archived patients are hidden
    from the list but kept)."""
    access = Access(user)
    access.patient_or_404(patient_id)
    changes = {k: (v.strip() if isinstance(v, str) else v)
               for k, v in body.model_dump().items() if v is not None}
    patient = records.patients.update(patient_id, **changes)
    return _patient_view(access, patient, registry.load())


@router.post("/patients/{patient_id}/merge")
async def merge_patient(body: Merge, request: Request, patient_id: str = PatientIdParam,
                        user: User = Depends(_patients)) -> dict:
    """Merge a duplicate record (typically one created when the person shared
    a policy) into another of this provider's records: shared policies,
    uploads, saved checklists and the account link move; the duplicate is
    deleted."""
    access = Access(user)
    source = access.patient_or_404(patient_id)
    target = access.patient_or_404(body.into_patient_id)
    if source.patient_id == target.patient_id:
        raise HTTPException(400, "Choose a different record to merge into")
    audit_patient(request, target.patient_id)
    entries = registry.load()
    for e in entries:
        if e.get("org_id") == user.org_id and e.get("patient_id") == source.patient_id:
            e["patient_id"] = target.patient_id
    registry.save(entries)
    for share in records.shares.all():
        if share.org_id == user.org_id and share.patient_id == source.patient_id:
            records.shares.update(share.share_id, patient_id=target.patient_id)
    for link in records.providers.all():
        if link.org_id == user.org_id and link.patient_id == source.patient_id:
            records.providers.update(link.provider_id, patient_id=target.patient_id)
    for c in records.checklists.all():
        if c.org_id == user.org_id and c.patient_id == source.patient_id:
            records.checklists.update(c.checklist_id, patient_id=target.patient_id)
    if source.linked_username and not target.linked_username:
        target = records.patients.update(target.patient_id, linked_username=source.linked_username)
    records.patients.remove(source.patient_id)
    # a fresh Access: the one above holds the shares as they were before the merge
    return _patient_view(Access(user), target, registry.load())


@router.delete("/patients/{patient_id}")
async def delete_patient(patient_id: str = PatientIdParam, user: User = Depends(_patients)) -> dict:
    """Delete the record, the documents the hospital uploaded for this patient
    and its saved checklists. Policies the patient shared are only unfiled:
    they belong to the patient."""
    from . import policies  # paths are read at call time so tests can redirect them

    access = Access(user)
    access.patient_or_404(patient_id)
    entries = registry.load()
    deleted = 0
    for e in entries:
        if e.get("org_id") == user.org_id and e.get("patient_id") == patient_id:
            documents.delete(e, policies.CHUNK_DIR, policies.UPLOAD_DIR)
            deleted += 1
    for share in records.shares.all():
        if share.org_id == user.org_id and share.patient_id == patient_id:
            records.shares.update(share.share_id, patient_id=None)
    for link in records.providers.all():
        if link.org_id == user.org_id and link.patient_id == patient_id:
            records.providers.update(link.provider_id, patient_id=None)
    for c in records.checklists.all():
        if c.patient_id == patient_id:
            records.checklists.remove(c.checklist_id)
    records.patients.remove(patient_id)
    return {"deleted": patient_id, "documents_deleted": deleted}


# ── Saved prior-authorization checklists ─────────────────────────────

class ChecklistItemIn(BaseModel):
    item_id: str = Field(max_length=40)
    category: str = Field(max_length=40)
    description: str = Field(max_length=300)
    required: bool = True
    completed: bool = False


class NewChecklist(BaseModel):
    document_id: str = Field(pattern=DOCUMENT_ID_PATTERN)
    service_name: str = Field(min_length=1, max_length=200)
    service_code: str = Field("", max_length=20)
    diagnosis_code: str = Field("", max_length=20)
    items: list[ChecklistItemIn] = Field(max_length=50)


class ChecklistChanges(BaseModel):
    items: list[ChecklistItemIn] = Field(max_length=50)


def _checklist_or_404(user: User, patient_id: str, checklist_id: str) -> records.Checklist:
    c = records.checklists.get(checklist_id)
    if c is None or c.org_id != user.org_id or c.patient_id != patient_id:
        raise HTTPException(404, "Checklist not found")
    return c


@router.get("/patients/{patient_id}/checklists")
async def list_checklists(patient_id: str = PatientIdParam, user: User = Depends(_patients)) -> list[dict]:
    Access(user).patient_or_404(patient_id)
    mine = [vars(c) for c in records.checklists.all()
            if c.org_id == user.org_id and c.patient_id == patient_id]
    return sorted(mine, key=lambda c: c["created_at"], reverse=True)


@router.post("/patients/{patient_id}/checklists")
async def save_checklist(body: NewChecklist, request: Request, patient_id: str = PatientIdParam,
                         user: User = Depends(_patients)) -> dict:
    """Save a generated checklist on the patient record (the policy must be
    one of this patient's documents)."""
    access = Access(user)
    access.patient_or_404(patient_id)
    if body.document_id not in access.patient_document_ids(registry.load(), patient_id):
        raise HTTPException(404, "Document not found")
    audit_patient(request, patient_id)
    audit_document(request, body.document_id)
    c = records.checklists.add(records.Checklist(
        records.new_id(), user.org_id, patient_id, body.document_id, body.service_name.strip(),
        body.service_code.strip(), body.diagnosis_code.strip(),
        [i.model_dump() for i in body.items], created_by=user.username))
    return vars(c)


@router.patch("/patients/{patient_id}/checklists/{checklist_id}")
async def update_checklist(body: ChecklistChanges, patient_id: str = PatientIdParam,
                           checklist_id: str = ChecklistIdParam,
                           user: User = Depends(_patients)) -> dict:
    _checklist_or_404(user, patient_id, checklist_id)
    return vars(records.checklists.update(
        checklist_id, items=[i.model_dump() for i in body.items],
        updated_at=datetime.now(UTC).isoformat()))


@router.delete("/patients/{patient_id}/checklists/{checklist_id}")
async def delete_checklist(patient_id: str = PatientIdParam, checklist_id: str = ChecklistIdParam,
                           user: User = Depends(_patients)) -> dict:
    _checklist_or_404(user, patient_id, checklist_id)
    records.checklists.remove(checklist_id)
    return {"deleted": checklist_id}


# ── Policies shared with this hospital ───────────────────────────────

class FileShare(BaseModel):
    patient_id: str | None = Field(None, pattern=DOCUMENT_ID_PATTERN)


def _shared_rows(user: User) -> list[dict]:
    entries = {e["document_id"]: e for e in registry.load()}
    cutoff = (datetime.now(UTC) - timedelta(days=NEW_SHARE_DAYS)).isoformat()
    names = {p.patient_id: p.name for p in records.patients.all() if p.org_id == user.org_id}
    rows = []
    for share in records.shares.all():
        if share.org_id != user.org_id or share.document_id not in entries:
            continue
        e = entries[share.document_id]
        sharer = user_store.get(share.shared_by)
        rows.append({"share_id": share.share_id, "document_id": share.document_id,
                     "filename": e.get("filename"), "plan_name": e.get("plan_name"),
                     "insurer_name": e.get("insurer_name"),
                     "shared_by": share.shared_by,
                     "shared_by_name": sharer.full_name if sharer else "",
                     "patient_id": share.patient_id, "patient_name": names.get(share.patient_id),
                     "created_at": share.created_at, "is_new": share.created_at >= cutoff})
    return sorted(rows, key=lambda r: r["created_at"], reverse=True)


@router.get("/shared")
async def list_shared(user: User = Depends(_patients)) -> list[dict]:
    """Policies individuals shared with this provider (newest first; those
    shared in the last NEW_SHARE_DAYS days are marked new)."""
    return _shared_rows(user)


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


# ── Patients who added this provider (connections) ───────────────────

def _connection_rows(user: User) -> list[dict]:
    """Individuals who added this provider to their providers: name and email
    only, and how many policies they chose to share."""
    cutoff = (datetime.now(UTC) - timedelta(days=NEW_SHARE_DAYS)).isoformat()
    names = {p.patient_id: p.name for p in records.patients.all() if p.org_id == user.org_id}
    shared = {}
    for share in records.shares.all():
        if share.org_id == user.org_id:
            shared[share.shared_by] = shared.get(share.shared_by, 0) + 1
    rows = []
    for link in records.providers.all():
        person = user_store.get(link.owner) if link.org_id == user.org_id else None
        if person is None:
            continue
        rows.append({"connection_id": link.provider_id, "email": person.username,
                     "name": person.full_name, "connected_at": link.connected_at,
                     "patient_id": link.patient_id, "patient_name": names.get(link.patient_id),
                     "shared_count": shared.get(person.username, 0),
                     "is_new": link.patient_id is None and link.connected_at >= cutoff})
    return sorted(rows, key=lambda r: r["connected_at"], reverse=True)


@router.get("/connections")
async def list_connections(user: User = Depends(_patients)) -> list[dict]:
    """Patients who added this provider (newest first)."""
    return _connection_rows(user)


@router.patch("/connections/{connection_id}")
async def file_connection(body: FileShare, request: Request,
                          connection_id: str = ConnectionIdParam,
                          user: User = Depends(_patients)) -> dict:
    """Attach a connection to one of this provider's patient records (or
    detach). The person's policies that are unfiled or filed under their
    previous record move to the new one, as do the ones they share later.
    The previous record is kept (merge it to remove it)."""
    link = records.providers.get(connection_id)
    if link is None or link.org_id != user.org_id:
        raise HTTPException(404, "Connection not found")
    if body.patient_id:
        Access(user).patient_or_404(body.patient_id)
        for share in records.shares.all():
            if (share.org_id == user.org_id and share.shared_by == link.owner
                    and share.patient_id in (None, link.patient_id)):
                records.shares.update(share.share_id, patient_id=body.patient_id)
    audit_target(request, link.owner)
    audit_patient(request, body.patient_id)
    records.providers.update(connection_id, patient_id=body.patient_id)
    return {"connection_id": connection_id, "patient_id": body.patient_id}


# ── Overview ─────────────────────────────────────────────────────────

@router.get("/overview")
async def overview(user: User = Depends(_patients)) -> dict:
    """The provider's landing page: patients, plans ended or ending soon,
    shares waiting to be filed, people who added the provider but aren't
    attached to a patient record yet."""
    access, entries = Access(user), registry.load()
    today = date.today()
    soon = (today + timedelta(days=ENDING_SOON_DAYS)).isoformat()
    patients = [p for p in records.patients.all() if p.org_id == user.org_id]
    active = [p for p in patients if not p.archived]
    ended, ending = [], []
    for p in active:
        for d in _patient_view(access, p, entries)["documents"]:
            end = d.get("expiration_date") or ""
            row = {"patient_id": p.patient_id, "patient_name": p.name, "document_id": d["document_id"],
                   "plan": d.get("display_name") or d.get("plan_name") or d["filename"],
                   "expiration_date": end}
            if d["coverage_status"] == "ended":
                ended.append(row)
            elif end and end <= soon:
                ending.append(row)
    shared = _shared_rows(user)
    unfiled = [r for r in shared if r["patient_id"] is None]
    new_connections = [r for r in _connection_rows(user) if r["patient_id"] is None]
    return {
        "patient_count": len(active), "archived_count": len(patients) - len(active),
        "plans_ended": sorted(ended, key=lambda r: r["expiration_date"]),
        "plans_ending_soon": sorted(ending, key=lambda r: r["expiration_date"]),
        "ending_soon_days": ENDING_SOON_DAYS,
        "recent_shares": [r for r in shared if r["is_new"]],
        "new_share_days": NEW_SHARE_DAYS,
        "unfiled_shares": unfiled,
        "unlinked_connections": new_connections,
    }


# ── Hospital profile ─────────────────────────────────────────────────

class OrgProfile(BaseModel):
    address: str = Field("", max_length=200)
    city: str = Field("", max_length=100)
    phone: str = Field("", max_length=30, pattern=r"^[0-9 +().-]*$")
    contact_email: str = Field("", max_length=254, pattern=r"^([^@\s]+@[^@\s]+\.[^@\s]+)?$")


def _profile(org: records.Org) -> dict:
    return {"org_id": org.org_id, "name": org.name, "address": org.address, "city": org.city,
            "phone": org.phone, "contact_email": org.contact_email}


@router.get("/profile")
async def get_profile(user: User = Depends(_patients)) -> dict:
    return _profile(records.orgs.get(user.org_id))


@router.patch("/profile")
async def update_profile(body: OrgProfile, admin: User = Depends(_staff_admin)) -> dict:
    """Hospital admins set the details individuals see when sharing."""
    changes = {k: v.strip() for k, v in body.model_dump().items()}
    return _profile(records.orgs.update(admin.org_id, **changes))


# ── Access log (hospital admins) ─────────────────────────────────────

@router.get("/access-log")
async def access_log(limit: int = Query(200, ge=1, le=1000),
                     include_routine: bool = Query(False),
                     admin: User = Depends(_staff_admin)) -> list[dict]:
    """This provider's staff activity from the audit log, newest first, in
    plain words: who opened which patient or document, asked, uploaded...
    Routine page loads are left out unless asked for. Never question text
    (the audit log doesn't hold it). Staff membership is as of now."""
    staff = {u.username for u in user_store.all() if u.org_id == admin.org_id}
    names = {p.patient_id: p.name for p in records.patients.all() if p.org_id == admin.org_id}
    rows = []
    for e in reversed(audit.read_entries()):
        if e.get("user") not in staff:
            continue
        label, routine = audit.describe(e)
        if routine and not include_routine:
            continue
        rows.append({k: e.get(k) for k in ("ts", "user", "method", "route", "document_id",
                                            "patient_id", "status")}
                    | {"patient_name": names.get(e.get("patient_id")), "label": label,
                       "routine": routine})
        if len(rows) >= limit:
            break
    return rows
