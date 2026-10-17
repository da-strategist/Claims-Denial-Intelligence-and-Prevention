from datetime import datetime
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse, Response

from app.data import (
    ClaimsRepository,
    ReferenceData,
    RuleRepository,
    get_reference_data,
    get_repository,
    get_rule_repository,
)
from app.data.registrations import RegistrationStore, get_registration_store
from app.models import (
    Claim,
    ClaimCreate,
    ClaimCreated,
    ClaimDetail,
    ClaimQuery,
    ClaimStatus,
    EdiFile,
    PayerType,
    Sex,
    Page,
    Permission,
    RecordStatus,
    Severity,
)
from app.models.common import ClaimId
from app.services import validation_engine
from app.services.auth import SignedIn, audit_note, require
from app.services.claim_pdf import claim_form_pdf, readable_837_pdf
from app.services.edi837 import ClaimParties, build_837
from app.services.edi_reader import read_837
from app.services.edi_settings import load_edi_settings
from app.services.status_snapshot import StatusSnapshot, get_status_snapshot

router = APIRouter(prefix="/api/claims", tags=["claims"], dependencies=[require(Permission.CLAIMS_READ)])

WRITE = [require(Permission.CLAIMS_WRITE)]

Claims = Annotated[ClaimsRepository, Depends(get_repository)]
Rules = Annotated[RuleRepository, Depends(get_rule_repository)]

Reference = Annotated[ReferenceData, Depends(get_reference_data)]
Registrations = Annotated[RegistrationStore, Depends(get_registration_store)]


@router.get("", response_model=Page[Claim])
def list_claims(
    query: Annotated[ClaimQuery, Query()],
    repo: Claims,
    rules: Rules,
    snapshot: Annotated[StatusSnapshot, Depends(get_status_snapshot)],
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
    user: SignedIn,
) -> ClaimCreated:
    """Enter a Draft claim for a registered patient and validate it.

    The department comes from the provider; each line's category (and, if omitted, its
    charge) from the CPT code set. The claim is saved, and its billing details update the
    patient's registration so their next claim starts from them.
    """
    audit_note(request, patient_id=body.patient_id)
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
    audit_note(request, claim_id=claim.claim_id)
    registrations.record_claim(
        patient,
        Sex(patient.gender) if patient.gender in Sex._value2member_map_ else Sex.UNKNOWN,
        body.billing,
        [body.payer_id, *body.other_payer_ids],
        user.username,
    )
    validation = validation_engine.validate_claims(
        repo.claims_frame([claim.claim_id]), rules.list()
    )[0]
    return ClaimCreated(claim=claim, validation=validation)


@router.post("/{claim_id}/submit", response_model=ClaimCreated, dependencies=WRITE)
def submit_claim(claim_id: ClaimId, repo: Claims, rules: Rules, request: Request) -> ClaimCreated:
    """Mark a Draft as submitted to the payer today.

    This is the only way a claim leaves Draft, whether it was entered on screen or through
    the API. The enabled rules run again now, and any error or warning blocks submission.
    The 837 claim file is created and saved with the claim (none for self-pay, which is
    billed to the patient).
    """
    claim = repo.get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    if claim.status != ClaimStatus.DRAFT:
        raise HTTPException(
            status_code=409,
            detail=f"Only draft claims can be submitted; {claim_id} is {claim.status}",
        )
    # Judge the claim as it goes out: today's date, not the planned one
    validation = validation_engine.validate_claims(repo.submission_frame(claim_id), rules.list())[0]
    blocking = [
        f"{f.rule_id} {f.rule_name}"
        for f in validation.findings
        if f.severity in (Severity.ERROR, Severity.WARNING)
    ]
    if blocking:
        raise HTTPException(
            status_code=422,
            detail=f"Resolve every rule error and warning before submitting: {'; '.join(blocking)}",
        )
    edi = None
    if claim.payer is None or claim.payer.payer_type != PayerType.SELF_PAY:
        edi = _build_837(claim, repo)
        audit_note(request, edi_control_number=edi[1].control_number)
    try:
        claim = repo.submit_claim(claim_id, edi=edi)
    except ValueError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err
    validation = validation_engine.validate_claims(repo.claims_frame([claim_id]), rules.list())[0]
    return ClaimCreated(claim=claim, validation=validation)


@router.get("/{claim_id}", response_model=ClaimDetail)
def get_claim(claim_id: ClaimId, repo: Claims, user: SignedIn) -> ClaimDetail:
    """Single claim with its lines, denials, payer, and provider, and the patient's
    demographics for roles allowed to see them."""
    claim = repo.get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
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


def _build_837(claim: ClaimDetail, repo: ClaimsRepository) -> tuple[str, EdiFile]:
    if claim.billing is None:
        raise HTTPException(
            status_code=422, detail=f"{claim.claim_id} has no billing details for the 837 file"
        )
    payers = [claim.payer, *[repo.get_payer(p) for p in claim.other_payer_ids]]
    facility = repo.get_facility(claim.facility_id)
    parties = ClaimParties(payers=payers, facility=facility, settings=load_edi_settings())
    return build_837(claim, parties, repo.next_control_number(), datetime.now())


def _next_id(ids: pd.Series, prefix: str, digits: int) -> str:
    """One past the highest existing ID: CLM0120000 -> CLM0120001."""
    highest = ids.str.removeprefix(prefix).astype("int64").max() if len(ids) else 0
    return f"{prefix}{int(highest) + 1:0{digits}d}"
