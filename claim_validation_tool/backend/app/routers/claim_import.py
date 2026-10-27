import base64
import binascii

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.data import repository as repository_module
from app.models import Permission
from app.models.claim_import import (
    MAX_IMPORT_BYTES,
    MAX_IMPORT_CLAIMS,
    ClaimImportRequest,
    ClaimImportResult,
    ImportedClaim,
    ImportFailure,
)
from app.routers.claims import add_draft_claim
from app.services import claim_import
from app.services.auth import SignedIn, audit_note, require
from app.services.edi_settings import load_edi_settings
from app.services.org_context import OrgClaims, OrgId, OrgReference, OrgRegistrations, OrgRules

router = APIRouter(
    prefix="/api/claims/import", tags=["claims"], dependencies=[require(Permission.CLAIMS_WRITE)]
)


@router.get(
    "/template.csv",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/csv": {}}, "description": "Column layout with an example claim"}},
)
def import_template() -> PlainTextResponse:
    """The CSV layout for uploading claims: one row per service line, grouped by claim_ref."""
    return PlainTextResponse(
        claim_import.template_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="claims_upload_template.csv"'},
    )


@router.post("", response_model=ClaimImportResult)
def import_claims(
    body: ClaimImportRequest,
    request: Request,
    repo: OrgClaims,
    rules: OrgRules,
    reference: OrgReference,
    registrations: OrgRegistrations,
    org_id: OrgId,
    user: SignedIn,
) -> ClaimImportResult:
    """Read a CSV/Excel file in the template's layout, or an X12 837P/837I, and save each
    claim in it as a Draft, checked as if it were entered on the form and then validated
    against the rules. Claims that can't be read or saved are listed with the reasons;
    the rest are saved. Nothing is submitted."""
    try:
        data = base64.b64decode(body.content, validate=True)
    except (binascii.Error, ValueError) as err:
        raise HTTPException(status_code=422, detail="The file's content isn't valid base64") from err
    if len(data) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail=f"Files can be up to {MAX_IMPORT_BYTES // (1024 * 1024)} MB")
    today = repository_module._today()
    try:
        kind = claim_import.file_type(body.filename, data)
        if kind == "837":
            text = data.decode("utf-8", errors="replace")
            payer_ids = load_edi_settings(org_id).payer_ids
            kind, parsed = claim_import.parse_837(text, repo, registrations, today, payer_ids)
        else:
            frame = claim_import.read_table(data, kind)
            parsed = claim_import.parse_table(frame, repo, registrations, today)
    except claim_import.ImportFileError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    if len(parsed) > MAX_IMPORT_CLAIMS:
        raise HTTPException(
            status_code=422,
            detail=f"The file has {len(parsed)} claims; upload up to {MAX_IMPORT_CLAIMS} at a time",
        )

    created, failed = [], []
    for item in parsed:
        if item.body is None:
            failed.append(ImportFailure(ref=item.ref, where=item.where, errors=item.errors))
            continue
        try:
            result = add_draft_claim(item.body, repo, rules, reference, registrations, user)
        except HTTPException as err:
            failed.append(ImportFailure(ref=item.ref, where=item.where, errors=[str(err.detail)]))
            continue
        created.append(
            ImportedClaim(
                ref=item.ref,
                where=item.where,
                claim=result.claim,
                validation=result.validation,
                notes=item.notes,
            )
        )
    audit_note(
        request,
        import_file_type=kind,
        claim_ids=[c.claim.claim_id for c in created],
        patient_ids=sorted({c.claim.patient_id for c in created}),
        failed=len(failed),
    )
    return ClaimImportResult(file_type=kind, claims_found=len(parsed), created=created, failed=failed)
