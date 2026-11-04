"""The signed-in user's organisation as a whole: its data export and settings (administrators)."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from app.data.api_keys import ApiKey, get_api_keys
from app.data.org_lifecycle import export_organisation
from app.data.orgs import get_org_registry
from app.models import OrganisationSettings, PayerType, Permission, RecordStatus
from app.services.auth import SignedIn, audit_note, require
from app.services.edi837 import facility_zip_gap
from app.services.edi_settings import EdiSettings, cleaned, load_edi_settings, save_edi_settings
from app.services.org_context import OrgClaims, OrgId

router = APIRouter(prefix="/api/organisation", tags=["organisation"])


@router.put(
    "/settings", response_model=OrganisationSettings, dependencies=[require(Permission.ORG_SETTINGS)]
)
def update_settings(body: OrganisationSettings, org_id: OrgId, request: Request) -> OrganisationSettings:
    """Which route the organisation's staff are offered first. Every claim can still take
    either route, so changing this affects no existing claim."""
    org = get_org_registry().set_default_claim_route(org_id, body.default_claim_route)
    audit_note(request, default_claim_route=org.default_claim_route.value)
    return OrganisationSettings(default_claim_route=org.default_claim_route)


class ApiKeySummary(BaseModel):
    """An API key as the Users page lists it (never the key itself)."""

    id: str
    name: str
    created_at: datetime
    created_by: str
    last_used_at: datetime | None
    revoked_at: datetime | None
    revoked_by: str | None


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60, description="Which system uses it, e.g. Epic test")

    @field_validator("name")
    @classmethod
    def _named(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name the system that will use this key")
        return value.strip()


class ApiKeyCreated(BaseModel):
    key: ApiKeySummary
    token: str = Field(description="The key itself. Shown this once and never again")


def _key_summary(key: ApiKey) -> ApiKeySummary:
    return ApiKeySummary.model_validate(key.model_dump())


@router.get(
    "/api-keys", response_model=list[ApiKeySummary], dependencies=[require(Permission.ORG_SETTINGS)]
)
def list_api_keys(org_id: OrgId) -> list[ApiKeySummary]:
    """The organisation's API keys, including revoked ones."""
    return [_key_summary(key) for key in get_api_keys().list(org_id)]


@router.post(
    "/api-keys",
    response_model=ApiKeyCreated,
    status_code=201,
    dependencies=[require(Permission.ORG_SETTINGS)],
)
def create_api_key(body: ApiKeyCreate, org_id: OrgId, user: SignedIn, request: Request) -> ApiKeyCreated:
    """A new key for one of the hospital's systems. It can send claims and read their results
    across the organisation, on /api/v1 only."""
    try:
        key, token = get_api_keys().create(org_id, body.name, user.username)
    except ValueError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err
    audit_note(request, api_key=key.id, api_key_name=key.name)
    return ApiKeyCreated(key=_key_summary(key), token=token)


@router.delete(
    "/api-keys/{key_id}", response_model=ApiKeySummary, dependencies=[require(Permission.ORG_SETTINGS)]
)
def revoke_api_key(key_id: str, org_id: OrgId, user: SignedIn, request: Request) -> ApiKeySummary:
    """Stop a key working, straight away. It stays listed so the audit log can be traced."""
    key = get_api_keys().revoke(org_id, key_id, user.username)
    if key is None:
        raise HTTPException(status_code=404, detail=f"No API key {key_id}")
    audit_note(request, api_key_name=key.name)
    return _key_summary(key)


class EdiSettingsStatus(BaseModel):
    """The settings, and what each kind of claim file still needs before it can be live."""

    settings: EdiSettings
    missing_for_handoff: list[str]
    missing_for_sending: list[str]


def _edi_status(settings: EdiSettings, repo) -> EdiSettingsStatus:
    payers = [p.payer_id for p in repo.list_payers() if p.payer_type != PayerType.SELF_PAY]
    facilities = [f for f in repo.list_facilities() if f.status == RecordStatus.ACTIVE]
    zip_gaps = [gap for gap in (facility_zip_gap(settings, f) for f in facilities) if gap]
    return EdiSettingsStatus(
        settings=settings,
        missing_for_handoff=[*settings.missing(payers, needs_clearinghouse=False), *zip_gaps],
        missing_for_sending=[*settings.missing(payers), *zip_gaps],
    )


def _changed(old: object, new: object, path: str = "") -> list[str]:
    """Names of the settings that differ, never their values."""
    if isinstance(old, dict) and isinstance(new, dict):
        return [
            name
            for key in sorted(old.keys() | new.keys())
            for name in _changed(old.get(key), new.get(key), f"{path}.{key}" if path else key)
        ]
    return [path] if (old or "") != (new or "") else []


@router.get(
    "/edi-settings", response_model=EdiSettingsStatus, dependencies=[require(Permission.ORG_SETTINGS)]
)
def get_edi_settings(org_id: OrgId, repo: OrgClaims) -> EdiSettingsStatus:
    """The organisation's identifiers for 837 claim files."""
    return _edi_status(load_edi_settings(org_id), repo)


@router.put(
    "/edi-settings", response_model=EdiSettingsStatus, dependencies=[require(Permission.ORG_SETTINGS)]
)
def update_edi_settings(
    body: EdiSettings, org_id: OrgId, repo: OrgClaims, request: Request
) -> EdiSettingsStatus:
    """Save the identifiers. Anything left blank keeps files marked as test files, and so does
    test mode, so these can be filled in over time. Files already created don't change."""
    settings, problems = cleaned(body)
    known = {
        "payer": {p.payer_id for p in repo.list_payers()},
        "facility": {f.facility_id for f in repo.list_facilities()},
    }
    problems += [f"Unknown payer {p}" for p in settings.payer_ids if p not in known["payer"]]
    problems += [f"Unknown facility {f}" for f in settings.facility_zip_codes if f not in known["facility"]]
    if problems:
        raise HTTPException(status_code=422, detail="; ".join(problems))
    before = load_edi_settings(org_id)
    save_edi_settings(org_id, settings)
    audit_note(request, changed=_changed(before.model_dump(), settings.model_dump()), mode=settings.mode)
    return _edi_status(settings, repo)


@router.get("/export", dependencies=[require(Permission.DATA_EXPORT)])
def export(org_id: OrgId, me: SignedIn, request: Request) -> Response:
    """Everything the organisation has here, decrypted, in one zip with a manifest. It holds
    PHI, so the download is recorded in the audit log with what it contained."""
    data, manifest = export_organisation(org_id, me.username)
    audit_note(request, files=len(manifest["files"]), bytes=len(data))
    name = f"{org_id}-export-{datetime.now(UTC):%Y%m%d-%H%M%S}.zip"
    return Response(
        data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"},
    )
