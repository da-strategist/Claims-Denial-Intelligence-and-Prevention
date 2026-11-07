from datetime import UTC, datetime
from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse, Response

from app.data import (
    ClaimsRepository,
)
from app.data.scoped import OutOfScopeError
from app.models import (
    Claim,
    ClaimCreate,
    ClaimCreated,
    ClaimDetail,
    ClaimQuery,
    ClaimStatus,
    EdiFile,
    HandoffExport,
    HandOffRequest,
    PayerType,
    ReopenRequest,
    Sex,
    Page,
    Permission,
    RecordStatus,
    Severity,
)
from app.models.common import ClaimId
from app.services import validation_engine
from app.services.auth import SignedIn, audit_note, require
from app.services import claim_changes
from app.services.claim_pdf import claim_changes_pdf, claim_form_pdf, readable_837_pdf
from app.services.edi837 import ClaimParties, billing_system_claim_number, build_837
from app.services.edi_reader import read_837
from app.services.edi_settings import load_edi_settings
from app.services.prior_auth import coverage_check, prior_auth_check
from app.services.org_context import (
    OrgClaimChanges,
    OrgClaims,
    OrgCorrections,
    OrgId,
    OrgPriorAuthLists,
    OrgReference,
    OrgRegistrations,
    OrgRules,
    OrgSnapshot,
)

router = APIRouter(prefix="/api/claims", tags=["claims"], dependencies=[require(Permission.CLAIMS_READ)])

WRITE = [require(Permission.CLAIMS_WRITE)]

Claims = OrgClaims
Rules = OrgRules

Reference = OrgReference
Registrations = OrgRegistrations


@router.get("", response_model=Page[Claim])
def list_claims(
    query: Annotated[ClaimQuery, Query()],
    repo: Claims,
    rules: Rules,
    snapshot: OrgSnapshot,
) -> Page[Claim]:
    """List claims with search, filtering, sorting, and pagination."""
    statuses = None
    if query.needs_attention is not None or query.sort_by == "risk_score":
        statuses = snapshot.get(repo, rules.list())
    return repo.list_claims(query, statuses)


@router.post(
    "", response_model=ClaimCreated, status_code=status.HTTP_201_CREATED, dependencies=WRITE
)
def create_claim(
    body: ClaimCreate,
    request: Request,
    repo: Claims,
    rules: Rules,
    reference: Reference,
    registrations: Registrations,
    pa_lists: OrgPriorAuthLists,
    user: SignedIn,
) -> ClaimCreated:
    """Enter a Draft claim for a registered patient and validate it.

    The department comes from the provider; each line's category (and, if omitted, its
    charge) from the CPT code set. The claim is saved, and its billing details update the
    patient's registration so their next claim starts from them.
    """
    audit_note(request, patient_id=body.patient_id)
    created = add_draft_claim(body, repo, rules, reference, registrations, pa_lists, user)
    audit_note(request, claim_id=created.claim.claim_id)
    return created


def add_draft_claim(
    body: ClaimCreate, repo, rules, reference, registrations, pa_lists, user, source_ref: str | None = None
) -> ClaimCreated:
    """Save a new Draft claim and validate it: shared by the form, the API and uploads.
    `source_ref` is the hospital's own number for an uploaded claim. Raises HTTPException
    when the claim can't be saved."""
    # Claim IDs are unique across the organisation, including claims outside this
    # person's access, so the next one comes from all of them
    claim_id = _next_id(repo.base.claims_frame()["claim_id"], "CLM", 7)
    fields, lines, patient = _claim_fields(body, claim_id, repo, reference, pa_lists)
    if source_ref:
        fields["source_ref"] = source_ref
    try:
        claim = repo.add_claim(fields, lines)
    except OutOfScopeError as err:
        raise HTTPException(status_code=403, detail=str(err)) from err
    except ValueError as err:  # another request took the same ID first
        raise HTTPException(status_code=409, detail=str(err)) from err
    _record_registration(registrations, patient, body, user)
    validation = validation_engine.validate_claims(
        repo.claims_frame([claim.claim_id]), rules.list()
    )[0]
    return ClaimCreated(claim=claim, validation=validation)


@router.put("/{claim_id}", response_model=ClaimCreated, dependencies=WRITE)
def update_claim(
    claim_id: ClaimId,
    body: ClaimCreate,
    request: Request,
    repo: Claims,
    rules: Rules,
    reference: Reference,
    registrations: Registrations,
    pa_lists: OrgPriorAuthLists,
    corrections: OrgCorrections,
    changes: OrgClaimChanges,
    user: SignedIn,
) -> ClaimCreated:
    """Correct a Draft claim entered in the app: the whole claim is given again, checked
    as when it was created, and replaces what was there (same ID, same patient). Its AI Fix
    corrections are folded in, since the form starts from the corrected values. Submitted
    claims can't change. The audit log records which fields changed."""
    result, changed = replace_draft_claim(
        claim_id, body, repo, rules, reference, registrations, pa_lists, corrections, changes, user
    )
    audit_note(request, changed=changed)
    return result


def replace_draft_claim(
    claim_id: str, body: ClaimCreate, repo, rules, reference, registrations, pa_lists, corrections, changes, user
) -> tuple[ClaimCreated, list[str]]:
    """Replace a Draft with the whole claim given again, and validate it: shared by the form
    and the claims API. Returns it with the names of the fields that changed. Raises
    HTTPException when it can't be replaced."""
    before = repo.get_claim(claim_id)
    if before is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    if before.status != ClaimStatus.DRAFT:
        raise HTTPException(
            status_code=409, detail=f"Only draft claims can be edited; {claim_id} is {before.status}"
        )
    fields, lines, patient = _claim_fields(body, claim_id, repo, reference, pa_lists)
    try:
        claim = repo.update_claim(fields, lines)
    except OutOfScopeError as err:
        raise HTTPException(status_code=403, detail=str(err)) from err
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    except ValueError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err
    folded = corrections.clear_claim(claim_id)
    if folded:
        repo.apply_overrides(corrections.overrides())
        claim = repo.get_claim(claim_id)
    changes.add(
        claim_id,
        [
            *claim_changes.correction_changes(folded),
            *claim_changes.edit_changes(
                claim_changes.claim_values(before, repo),
                claim_changes.claim_values(claim, repo),
                user.username,
                datetime.now(UTC),
            ),
        ],
    )
    _record_registration(registrations, patient, body, user)
    validation = validation_engine.validate_claims(repo.claims_frame([claim_id]), rules.list())[0]
    return ClaimCreated(claim=claim, validation=validation), _changed_fields(before, claim)


# Compared to tell the audit log what an edit changed (names only, never values: PHI)
_EDITABLE = (
    "payer_id", "other_payer_ids", "provider_id", "facility_id", "claim_type", "place_of_service",
    "service_date", "submission_date", "primary_icd10", "additional_icd10", "pa_required", "pa_obtained",
    "pa_number", "total_charge", "billing",
)


def _changed_fields(before: ClaimDetail, after: ClaimDetail) -> list[str]:
    old, new = before.model_dump(mode="json"), after.model_dump(mode="json")
    changed = [f for f in _EDITABLE if old.get(f) != new.get(f)]
    strip = lambda ls: [{k: v for k, v in line.items() if k not in ("line_id", "claim_id")} for line in ls]  # noqa: E731
    if strip(old["lines"]) != strip(new["lines"]):
        changed.append("lines")
    return changed


def _record_registration(registrations, patient, body: ClaimCreate, user) -> None:
    """The billing details update the patient's registration for their next claim."""
    registrations.record_claim(
        patient,
        Sex(patient.gender) if patient.gender in Sex._value2member_map_ else Sex.UNKNOWN,
        body.billing,
        [body.payer_id, *body.other_payer_ids],
        user.username,
    )


def _claim_fields(body: ClaimCreate, claim_id: str, repo, reference, pa_lists) -> tuple[dict, list[dict], Any]:
    """Check a claim's details against the organisation's registries and code sets, and
    build its fact_claims fields and lines. Raises 422 on anything unknown or inactive."""
    patient = repo.get_patient(body.patient_id)
    if patient is None or patient.status != RecordStatus.ACTIVE:
        raise HTTPException(
            status_code=422, detail=f"Patient {body.patient_id} is not a registered patient"
        )
    payers = [repo.get_payer(payer_id) for payer_id in (body.payer_id, *body.other_payer_ids)]
    for payer_id, payer in zip((body.payer_id, *body.other_payer_ids), payers):
        if payer is None:
            raise HTTPException(status_code=422, detail=f"Unknown payer {payer_id}")
    # Self-pay is billed to the patient; every insurer needs the member's policy
    if payers[0].payer_type != PayerType.SELF_PAY and body.billing.policy is None:
        raise HTTPException(
            status_code=422,
            detail=f"Give the member ID for {payers[0].payer_name} (billing.policy)",
        )
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
                "revenue_code": line.revenue_code,
            }
        )

    header = body.model_dump(mode="json", exclude={"diagnoses", "lines"})
    fields = {
        **header,
        "claim_id": claim_id,
        # The payer's list decides; the claim can add to it, but can't talk its way out of it
        "pa_required": body.pa_required
        or bool(pa_lists.listed_codes(body.payer_id, [line.cpt_code for line in body.lines])),
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
    return fields, lines, patient


@router.post("/{claim_id}/submit", response_model=ClaimCreated, dependencies=WRITE)
def submit_claim(
    claim_id: ClaimId, repo: Claims, rules: Rules, request: Request, org_id: OrgId
) -> ClaimCreated:
    """Mark a Draft as submitted to the payer today.

    This is the only way a claim leaves Draft, whether it was entered on screen or through
    the API. The enabled rules run again now, and any error or warning blocks submission.
    The 837 claim file is created and saved with the claim (none for self-pay, which is
    billed to the patient).
    """
    claim = repo.get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    if claim.status == ClaimStatus.HANDED_OFF:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{claim_id} was handed off to your billing system. Sending it here too could "
                "reach the payer twice; reopen it first if your billing system hasn't sent it."
            ),
        )
    if claim.status != ClaimStatus.DRAFT:
        raise HTTPException(
            status_code=409,
            detail=f"Only draft claims can be submitted; {claim_id} is {claim.status}",
        )
    blocking = _open_issues(claim_id, repo, rules)
    if blocking:
        raise HTTPException(
            status_code=422,
            detail=f"Resolve every rule error and warning before submitting: {'; '.join(blocking)}",
        )
    edi = None
    if claim.payer is None or claim.payer.payer_type != PayerType.SELF_PAY:
        edi = _build_837(claim, repo, org_id)
        audit_note(request, edi_control_number=edi[1].control_number)
    try:
        claim = repo.submit_claim(claim_id, edi=edi)
    except ValueError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err
    validation = validation_engine.validate_claims(repo.claims_frame([claim_id]), rules.list())[0]
    return ClaimCreated(claim=claim, validation=validation)


@router.post("/{claim_id}/hand-off", response_model=ClaimCreated, dependencies=WRITE)
def hand_off_claim(
    claim_id: ClaimId,
    repo: Claims,
    rules: Rules,
    request: Request,
    user: SignedIn,
    body: HandOffRequest = HandOffRequest(),
) -> ClaimCreated:
    """Finish a Draft here because the hospital sends it from its own billing system. Nothing
    goes to a payer and no 837 is created. The hospital may fix what's left over there, so
    open errors and warnings don't block this, but they must be acknowledged and are kept
    with the claim and in the audit log."""
    claim = repo.get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    if claim.status != ClaimStatus.DRAFT:
        raise HTTPException(
            status_code=409, detail=f"Only draft claims can be handed off; {claim_id} is {claim.status}"
        )
    open_issues = _open_issues(claim_id, repo, rules)
    if open_issues and not body.acknowledge_open_issues:
        raise HTTPException(
            status_code=422,
            detail=f"Confirm you're handing off this claim with open issues: {'; '.join(open_issues)}",
        )
    audit_note(request, open_issues=open_issues)
    try:
        claim = repo.hand_off_claim(claim_id, user.username, open_issues)
    except ValueError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err
    validation = validation_engine.validate_claims(repo.claims_frame([claim_id]), rules.list())[0]
    return ClaimCreated(claim=claim, validation=validation)


@router.post("/{claim_id}/reopen", response_model=ClaimCreated, dependencies=WRITE)
def reopen_claim(
    claim_id: ClaimId, body: ReopenRequest, repo: Claims, rules: Rules, request: Request
) -> ClaimCreated:
    """Put a handed-off claim back to Draft, so it can be changed or sent from here. Someone
    must confirm the billing system hasn't sent it, or the payer could receive it twice."""
    if not body.confirmed_not_sent:
        raise HTTPException(
            status_code=422, detail="Confirm your billing system hasn't sent this claim before reopening it"
        )
    try:
        claim = repo.reopen_claim(claim_id)
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    except ValueError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err
    audit_note(request, confirmed_not_sent=True)
    validation = validation_engine.validate_claims(repo.claims_frame([claim_id]), rules.list())[0]
    return ClaimCreated(claim=claim, validation=validation)


def _open_issues(claim_id: str, repo: ClaimsRepository, rules: Rules) -> list[str]:
    """Rule errors and warnings on the claim as it leaves: today's date, not the planned one."""
    validation = validation_engine.validate_claims(repo.submission_frame(claim_id), rules.list())[0]
    return [
        f"{f.rule_id} {f.rule_name}"
        for f in validation.findings
        if f.severity in (Severity.ERROR, Severity.WARNING)
    ]


@router.get("/{claim_id}", response_model=ClaimDetail)
def get_claim(claim_id: ClaimId, repo: Claims, pa_lists: OrgPriorAuthLists, user: SignedIn) -> ClaimDetail:
    """Single claim with its lines, denials, payer, and provider, what its checks did and
    didn't cover, and the patient's demographics for roles allowed to see them."""
    claim = repo.get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    claim = claim.model_copy(
        update={"prior_auth_check": prior_auth_check(claim, pa_lists), "coverage_check": coverage_check(claim)}
    )
    if not user.can(Permission.PATIENTS_READ):
        claim = claim.model_copy(update={"patient": None, "billing": None})
    return claim


@router.get(
    "/{claim_id}/837",
    response_class=PlainTextResponse,
    dependencies=WRITE,
    responses={200: {"content": {"text/plain": {}}, "description": "The X12 837 file"}},
)
def download_837(claim_id: ClaimId, repo: Claims, request: Request) -> PlainTextResponse:
    """The 837 a claim was submitted with. It holds the patient's full details, so only
    roles that change claims can download it, and each download is in the audit log."""
    claim, text = _submitted_837(claim_id, repo)
    audit_note(request, export=claim.edi.transaction)
    filename = f"{claim_id}_{claim.edi.transaction}{_test_suffix(claim)}.txt"
    return PlainTextResponse(
        text, headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get(
    "/{claim_id}/claim-form.pdf",
    response_class=Response,
    dependencies=WRITE,
    responses={200: {"content": {"application/pdf": {}}, "description": "CMS-1500 or UB-04 layout"}},
)
def download_claim_form(
    claim_id: ClaimId, repo: Claims, reference: Reference, request: Request
) -> Response:
    """The submitted claim on a CMS-1500 (professional) or UB-04 (institutional) layout,
    built from the saved 837. A reference copy for reading and printing."""
    claim, text = _submitted_837(claim_id, repo)
    parsed = read_837(text)
    procedures = {code: row.get("description", "") for code, row in reference.cpt.items()}
    form = "UB-04" if parsed.institutional else "CMS-1500"
    audit_note(request, export=f"{form} PDF")
    return _pdf(claim_form_pdf(parsed, procedures), f"{claim_id}_{form}{_test_suffix(claim)}.pdf")


@router.get(
    "/{claim_id}/837-readable.pdf",
    response_class=Response,
    dependencies=WRITE,
    responses={200: {"content": {"application/pdf": {}}, "description": "The 837, decoded"}},
)
def download_readable_837(claim_id: ClaimId, repo: Claims, request: Request) -> Response:
    """The saved 837 in named sections, each value with where it sits in the file."""
    claim, text = _submitted_837(claim_id, repo)
    audit_note(request, export=f"{claim.edi.transaction} readable PDF")
    return _pdf(readable_837_pdf(read_837(text)), f"{claim_id}_{claim.edi.transaction}_readable{_test_suffix(claim)}.pdf")


@router.get("/{claim_id}/handoff", response_model=HandoffExport, dependencies=WRITE)
def get_handoff_export(
    claim_id: ClaimId, repo: Claims, corrections: OrgCorrections, changes: OrgClaimChanges, org_id: OrgId
) -> HandoffExport:
    """What a handed-off claim takes back to the billing system: what changed here, what's
    still open, and whether its 837 is a test file. Nothing is exported by reading this."""
    claim = _handed_off(claim_id, repo)
    return _handoff_export(claim, repo, corrections, changes, org_id)


@router.get(
    "/{claim_id}/handoff/837",
    response_class=PlainTextResponse,
    dependencies=WRITE,
    responses={200: {"content": {"text/plain": {}}, "description": "The X12 837 file"}},
)
def download_handoff_837(
    claim_id: ClaimId, repo: Claims, request: Request, org_id: OrgId
) -> PlainTextResponse:
    """The handed-off claim, with its corrections, as an 837 for the billing system to import.
    Only after hand-off, so the claim can't change under the file or also be sent from here.
    It's a first-time claim (frequency 1): nothing has reached a payer. Each download is in
    the audit log."""
    claim = _handed_off(claim_id, repo)
    if _is_self_pay(claim):
        raise HTTPException(status_code=404, detail=f"{claim_id} is self-pay, so it has no 837 file")
    number = repo.handoff_control_number(claim_id)
    text, edi = _handoff_837(claim, repo, org_id, number)
    audit_note(request, export=f"{edi.transaction} hand-off", edi_control_number=edi.control_number, test_file=edi.test)
    suffix = "_TEST" if edi.test else ""
    return PlainTextResponse(
        text,
        headers={"Content-Disposition": f'attachment; filename="{claim_id}_{edi.transaction}_handoff{suffix}.txt"'},
    )


@router.get(
    "/{claim_id}/handoff/changes.pdf",
    response_class=Response,
    dependencies=WRITE,
    responses={200: {"content": {"application/pdf": {}}, "description": "What changed on the claim"}},
)
def download_handoff_changes(
    claim_id: ClaimId,
    repo: Claims,
    corrections: OrgCorrections,
    changes: OrgClaimChanges,
    request: Request,
    org_id: OrgId,
) -> Response:
    """The list of what changed on a handed-off claim and what's still open."""
    claim = _handed_off(claim_id, repo)
    export = _handoff_export(claim, repo, corrections, changes, org_id)
    audit_note(request, export="hand-off changes PDF", changes=[c.field for c in export.changes])
    return _pdf(claim_changes_pdf(claim, export), f"{claim_id}_changes.pdf")


def _handed_off(claim_id: str, repo: ClaimsRepository) -> ClaimDetail:
    claim = repo.get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    if claim.status != ClaimStatus.HANDED_OFF:
        raise HTTPException(
            status_code=409, detail=f"Only handed-off claims can be exported; {claim_id} is {claim.status}"
        )
    return claim


def _is_self_pay(claim: ClaimDetail) -> bool:
    return claim.payer is not None and claim.payer.payer_type == PayerType.SELF_PAY


def _handoff_837(claim: ClaimDetail, repo: ClaimsRepository, org_id: str, number: int) -> tuple[str, EdiFile]:
    return _build_837(claim, repo, org_id, number, billing_system_claim_number(claim.source_ref), handoff=True)


def _handoff_export(claim: ClaimDetail, repo, corrections, changes, org_id: str) -> HandoffExport:
    # A summary only: the control number is taken when the file is actually downloaded
    edi = None
    if not _is_self_pay(claim):
        edi = _handoff_837(claim, repo, org_id, claim.handoff.control_number or 0)[1]
    return HandoffExport(
        claim_id=claim.claim_id,
        source_ref=claim.source_ref,
        changes=claim_changes.net_changes(
            [
                *changes.for_claim(claim.claim_id),
                *claim_changes.correction_changes(corrections.for_claim(claim.claim_id)),
            ]
        ),
        open_issues=claim.handoff.open_issues,
        edi=edi,
    )


def _submitted_837(claim_id: str, repo: ClaimsRepository) -> tuple[ClaimDetail, str]:
    claim = repo.get_claim(claim_id)
    text = repo.edi_text(claim_id) if claim else None
    if claim is None or text is None or claim.edi is None:
        raise HTTPException(status_code=404, detail=f"No 837 file for {claim_id}")
    return claim, text


def _test_suffix(claim: ClaimDetail) -> str:
    return "_TEST" if claim.edi and claim.edi.test else ""


def _pdf(content: bytes, filename: str) -> Response:
    return Response(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_837(
    claim: ClaimDetail,
    repo: ClaimsRepository,
    org_id: str,
    control_number: int | None = None,
    claim_number: str | None = None,
    handoff: bool = False,
) -> tuple[str, EdiFile]:
    if claim.billing is None:
        raise HTTPException(
            status_code=422, detail=f"{claim.claim_id} has no billing details for the 837 file"
        )
    payers = [claim.payer, *[repo.get_payer(p) for p in claim.other_payer_ids]]
    facility = repo.get_facility(claim.facility_id)
    parties = ClaimParties(payers=payers, facility=facility, settings=load_edi_settings(org_id))
    number = repo.next_control_number() if control_number is None else control_number
    return build_837(claim, parties, number, datetime.now(), claim_number, handoff)


def _next_id(ids: pd.Series, prefix: str, digits: int) -> str:
    """One past the highest existing ID: CLM0120000 -> CLM0120001."""
    highest = ids.str.removeprefix(prefix).astype("int64").max() if len(ids) else 0
    return f"{prefix}{int(highest) + 1:0{digits}d}"
