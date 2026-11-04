"""The claims API for hospital systems (/api/v1): send a claim, get back its errors and
suggested fixes. It reaches the same Draft claims, rules and fixes as the screens and file
upload, so staff see what a system sent.

Signing in is by API key only (services/auth.py), and that key reaches nothing else. Nothing
here goes to a payer. The hospital's own claim number identifies a claim: sending the same
number again replaces the Draft and checks it again, so a system can correct a claim, or
retry after a dropped connection, without making a second one.

The claim number never goes in a URL or the audit log: it can be a patient account number.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.data import repository as repository_module

from app.models import ClaimCreate, ClaimStatus, HandOffRequest, Permission, Severity, Sex
from app.models.aifix import FixSuggestion
from app.models.claim_import import ClaimImportRequest, ImportFailure, ImportFileType
from app.models.common import ClaimId, PatientId
from app.models.rule import RuleFinding
from app.routers.aifix import AiFixDeps
from app.routers.claim_import import read_claims_file
from app.routers.claims import _open_issues, add_draft_claim, hand_off_claim, replace_draft_claim
from app.services import aifix
from app.services.auth import SignedIn, audit_note, require
from app.services.patient_list import (
    UNRESOLVED_PATIENT,
    IncomingPatient,
    ResolvedPatient,
    resolve_patient,
    save_lock,
    update_known,
)
from app.services.org_context import (
    OrgClaimChanges,
    OrgClaims,
    OrgCorrections,
    OrgId,
    OrgReference,
    OrgRegistrations,
    OrgRules,
)

router = APIRouter(prefix="/api/v1/claims", tags=["claims API"], dependencies=[require(Permission.CLAIMS_WRITE)])

ClaimNumber = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=38)]


class ApiPatient(BaseModel):
    """The patient as the hospital has them. Their date of birth, address and member ID are
    in `billing`. Added to the patient list if they aren't on it yet."""

    first_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    last_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    sex: Sex = Sex.UNKNOWN


class ApiClaim(ClaimCreate):
    """A claim in this API's own layout. The patient is `patient`, or `patient_id` if the
    system already holds this service's ID for them."""

    claim_number: ClaimNumber = Field(description="The hospital's own number for this claim")
    patient_id: PatientId | None = None
    patient: ApiPatient | None = None

    @model_validator(mode="after")
    def _one_patient(self) -> "ApiClaim":
        if (self.patient_id is None) == (self.patient is None):
            raise ValueError("Give either patient or patient_id")
        return self

    def incoming(self) -> IncomingPatient | None:
        if self.patient is None:
            return None
        return IncomingPatient(
            first_name=self.patient.first_name,
            last_name=self.patient.last_name,
            birth_date=self.billing.patient_birth_date,
            payer_id=self.payer_id,
            member_id=self.billing.policy.member_id if self.billing.policy else "",
            sex=self.patient.sex.value,
            zip_code=self.billing.patient_address.zip_code,
            primary_payer_id=None if self.other_payer_ids else self.payer_id,
        )


class ClaimCheck(BaseModel):
    """What was found on a claim. No patient details: the sender already has them."""

    claim_id: str = Field(description="This service's ID, for reading the claim again")
    claim_number: str | None
    action: Literal["created", "replaced", "none"] = Field(
        description="What this request did to the claim: 'none' when only reading it"
    )
    patient_id: str = Field(description="This service's ID for the patient")
    patient_added: bool = Field(description="True when this request added the patient to the list")
    patient_needs_review: bool = Field(
        description="True when the patient may be someone already on the list; a person will check"
    )
    status: ClaimStatus
    clean: bool = Field(description="True when no rule error or warning is open")
    open_issues: list[str] = Field(description="The rule errors and warnings still open")
    risk_score: int
    findings: list[RuleFinding]
    suggestions: list[FixSuggestion]


class FileCheck(BaseModel):
    file_type: ImportFileType
    claims_found: int
    checked: list[ClaimCheck]
    failed: list[ImportFailure]


class Sender:
    """Everything needed to save a claim and report on it."""

    def __init__(
        self,
        repo: OrgClaims,
        rules: OrgRules,
        reference: OrgReference,
        registrations: OrgRegistrations,
        corrections: OrgCorrections,
        changes: OrgClaimChanges,
        fixes: AiFixDeps,
        org_id: OrgId,
        user: SignedIn,
    ) -> None:
        self.repo, self.rules, self.reference, self.registrations = repo, rules, reference, registrations
        self.corrections, self.changes, self.fixes, self.org_id, self.user = corrections, changes, fixes, org_id, user

    def save(self, number: str, body: ClaimCreate, incoming: IncomingPatient | None) -> tuple[str, str, bool]:
        """Create the claim, or replace the Draft with this number, keeping the patient list
        up to date. Returns its ID, what was done, and whether the patient was added. Raises
        HTTPException if it can't be saved, and then the list is left as it was."""
        with save_lock(self.org_id):
            existing = self.repo.claim_id_for_number(number)
            draft = self.repo.get_claim(existing) if existing else None
            if existing is not None and (draft is None or draft.status != ClaimStatus.DRAFT):
                state = f"is {draft.status}" if draft else "exists"
                raise HTTPException(
                    status_code=409,
                    detail=f"This claim number was already used by {existing}, which {state}, so it can't be replaced",
                )
            resolved = self._patient(incoming, draft)
            if resolved is not None:
                body = body.model_copy(update={"patient_id": resolved.patient_id})
            try:
                if draft is None:
                    made = add_draft_claim(
                        body, self.repo, self.rules, self.reference, self.registrations, self.user, source_ref=number
                    )
                    claim_id, action = made.claim.claim_id, "created"
                else:
                    replace_draft_claim(
                        existing, body, self.repo, self.rules, self.reference, self.registrations,
                        self.corrections, self.changes, self.user,
                    )
                    claim_id, action = existing, "replaced"
            except HTTPException:
                if resolved is not None:
                    resolved.undo()
                raise
            return claim_id, action, bool(resolved and resolved.added)

    def _patient(self, incoming: IncomingPatient | None, draft) -> ResolvedPatient | None:
        today = repository_module._today()
        if incoming is None:
            return None
        if draft is None:
            return resolve_patient(incoming, self.repo, self.registrations, today, self.user.username)
        # The same claim sent again is the same patient, even if it corrects how they're
        # spelled or their date of birth. Unless nothing about them matches.
        patient = self.repo.get_patient(draft.patient_id)
        billing = draft.billing
        same_name = patient.last_name.casefold() == incoming.last_name.strip().casefold()
        same_birth = billing is not None and billing.patient_birth_date == incoming.birth_date
        if not (same_name or same_birth):
            raise HTTPException(
                status_code=409,
                detail=f"This claim number belongs to {draft.claim_id}, for a different patient. "
                "A claim's patient can't change; use a new claim number",
            )
        rename = self.repo.patient_added_from_claim(draft.patient_id)
        return update_known(patient, incoming, self.repo, today, rename=rename)

    def check(self, claim_id: str, action: str, patient_added: bool = False) -> ClaimCheck:
        fixes = aifix.claim_fixes(claim_id, *self.fixes.args)
        claim = self.repo.get_claim(claim_id)
        if fixes is None or claim is None:
            raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
        if claim.status == ClaimStatus.DRAFT:
            open_issues = _open_issues(claim_id, self.repo, self.rules)
        elif claim.handoff:
            open_issues = claim.handoff.open_issues
        else:
            open_issues = [
                f"{f.rule_id} {f.rule_name}"
                for f in fixes.validation.findings
                if f.severity in (Severity.ERROR, Severity.WARNING)
            ]
        return ClaimCheck(
            claim_id=claim_id,
            claim_number=claim.source_ref,
            action=action,
            patient_id=claim.patient_id,
            patient_added=patient_added,
            patient_needs_review=claim.patient_id in self.repo.patients_to_review(),
            status=claim.status,
            clean=not open_issues,
            open_issues=open_issues,
            risk_score=fixes.validation.risk_score,
            findings=fixes.validation.findings,
            suggestions=fixes.suggestions,
        )


Deps = Annotated[Sender, Depends()]


@router.post("", response_model=ClaimCheck)
def send_claim(body: ApiClaim, request: Request, sender: Deps) -> ClaimCheck:
    """Check one claim: saved as a Draft under its claim number, then validated. Sending the
    number again replaces that Draft, until it's handed off."""
    fields = body.model_dump(exclude={"claim_number", "patient"})
    fields["patient_id"] = fields["patient_id"] or UNRESOLVED_PATIENT
    claim_id, action, added = sender.save(body.claim_number, ClaimCreate.model_validate(fields), body.incoming())
    result = sender.check(claim_id, action, added)
    audit_note(
        request, claim_id=claim_id, patient_id=result.patient_id, action_taken=action,
        patient_added=added, clean=result.clean,
    )
    return result


@router.post("/file", response_model=FileCheck)
def send_file(body: ClaimImportRequest, request: Request, sender: Deps) -> FileCheck:
    """Check every claim in an X12 837P/837I, or a CSV/Excel file in the upload template's
    layout, up to 200. Each claim's own number (CLM01 or claim_ref) works as in POST /claims.
    A claim that can't be read or saved is listed with why; the others still go through."""
    kind, parsed = read_claims_file(body, sender.repo, sender.registrations, sender.org_id)
    numbers = [item.ref for item in parsed]
    checked, failed = [], []
    for item in parsed:
        problem = list(item.errors)
        if not item.ref and not problem:
            problem = ["The claim has no claim number"]
        elif numbers.count(item.ref) > 1:
            problem = ["This claim number appears more than once in the file", *problem]
        if problem or item.body is None:
            failed.append(ImportFailure(ref=item.ref, where=item.where, errors=problem))
            continue
        try:
            claim_id, action, added = sender.save(item.ref, item.body, item.incoming)
        except HTTPException as err:
            failed.append(ImportFailure(ref=item.ref, where=item.where, errors=[str(err.detail)]))
            continue
        checked.append(sender.check(claim_id, action, added))
    audit_note(
        request,
        import_file_type=kind,
        claim_ids=[c.claim_id for c in checked],
        patients_added=[c.patient_id for c in checked if c.patient_added],
        failed=len(failed),
    )
    return FileCheck(file_type=kind, claims_found=len(parsed), checked=checked, failed=failed)


@router.get("/{claim_id}", response_model=ClaimCheck)
def read_claim(claim_id: ClaimId, sender: Deps) -> ClaimCheck:
    """A claim's status, errors and suggested fixes as they are now."""
    return sender.check(claim_id, "none")


@router.post("/{claim_id}/handoff", response_model=ClaimCheck)
def hand_off(
    claim_id: ClaimId, request: Request, sender: Deps, body: HandOffRequest = HandOffRequest()
) -> ClaimCheck:
    """The hospital's system is sending this claim itself, so it's finished here. Open errors
    and warnings must be acknowledged with acknowledge_open_issues, and are kept with it.
    Only a person can reopen it, from the claim's page."""
    hand_off_claim(claim_id, sender.repo, sender.rules, request, sender.user, body)
    return sender.check(claim_id, "none")
