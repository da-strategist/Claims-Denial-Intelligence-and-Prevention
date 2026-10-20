
from fastapi import APIRouter, HTTPException, Request, Response, status

from app.data.scoped import ScopedClaims
from app.models import (
    DraftForm,
    Permission,
    SavedDraft,
    SavedDraftDetail,
    SavedDraftSummary,
)
from app.models.draft import DraftId
from app.services.auth import SignedIn, audit_note, require
from app.services.org_context import OrgClaims, OrgDrafts

# Saved drafts are unfinished claim entry: shared by everyone who can enter claims
router = APIRouter(
    prefix="/api/drafts", tags=["drafts"], dependencies=[require(Permission.CLAIMS_WRITE)]
)

Drafts = OrgDrafts
Claims = OrgClaims


def _not_found(draft_id: str) -> HTTPException:
    return HTTPException(
        status_code=404, detail=f"Saved draft {draft_id} not found (it may have expired)"
    )


@router.get("", response_model=list[SavedDraftSummary])
def list_drafts(drafts: Drafts, claims: Claims) -> list[SavedDraftSummary]:
    """Unexpired saved drafts, most recently saved first."""
    rows = []
    for draft in drafts.list():
        if not _in_scope(draft.form, claims):
            continue
        patient = claims.get_patient(draft.form.patient_id) if draft.form.patient_id else None
        rows.append(
            SavedDraftSummary(
                id=draft.id,
                patient_id=draft.form.patient_id,
                patient_name=f"{patient.first_name} {patient.last_name}" if patient else None,
                lines=sum(1 for line in draft.form.lines if line.cpt_code),
                updated_by=draft.updated_by,
                updated_at=draft.updated_at,
                expires_at=draft.expires_at,
            )
        )
    return rows


@router.get("/{draft_id}", response_model=SavedDraftDetail)
def get_draft(draft_id: DraftId, drafts: Drafts, claims: Claims, request: Request) -> SavedDraftDetail:
    """A saved draft with its patient, for reopening the form."""
    draft = drafts.get(draft_id)
    if draft is None or not _in_scope(draft.form, claims):
        raise _not_found(draft_id)
    audit_note(request, patient_id=draft.form.patient_id)
    patient = claims.get_patient(draft.form.patient_id) if draft.form.patient_id else None
    return SavedDraftDetail(**draft.model_dump(), patient=patient)


def _known_patient(form: DraftForm, claims: ScopedClaims) -> None:
    if form.patient_id and claims.get_patient(form.patient_id) is None:
        raise HTTPException(status_code=422, detail=f"Patient {form.patient_id} is not registered")
    if not _in_scope(form, claims):
        raise HTTPException(status_code=403, detail="That provider and facility are outside your access")


def _in_scope(form: DraftForm, claims: ScopedClaims) -> bool:
    """Visible to the account: inside its access, or no provider chosen yet (unassigned
    work anyone in the organisation may pick up)."""
    if form.provider_id is None:
        return True
    provider = claims.get_provider(form.provider_id)
    department = provider.department_id if provider else None
    return claims.scope.allows(form.facility_id, department, form.provider_id)


@router.post("", response_model=SavedDraft, status_code=status.HTTP_201_CREATED)
def create_draft(
    form: DraftForm, drafts: Drafts, claims: Claims, user: SignedIn, request: Request
) -> SavedDraft:
    """Save an unfinished claim form. Nothing is validated beyond the field formats."""
    _known_patient(form, claims)
    draft = drafts.create(form, user.username)
    audit_note(request, draft_id=draft.id, patient_id=form.patient_id)
    return draft


@router.put("/{draft_id}", response_model=SavedDraft)
def update_draft(
    draft_id: DraftId,
    form: DraftForm,
    drafts: Drafts,
    claims: Claims,
    user: SignedIn,
    request: Request,
) -> SavedDraft:
    """Save the form again; this restarts the draft's expiry clock."""
    existing = drafts.get(draft_id)
    if existing is None or not _in_scope(existing.form, claims):
        raise _not_found(draft_id)
    _known_patient(form, claims)
    draft = drafts.update(draft_id, form, user.username)
    if draft is None:
        raise _not_found(draft_id)
    audit_note(request, patient_id=form.patient_id)
    return draft


@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft(draft_id: DraftId, drafts: Drafts, claims: Claims) -> Response:
    """Discard a saved draft, or remove it once its claim has been created."""
    existing = drafts.get(draft_id)
    if existing is None or not _in_scope(existing.form, claims) or not drafts.delete(draft_id):
        raise _not_found(draft_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
