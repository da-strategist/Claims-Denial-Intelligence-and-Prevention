"""Platform administration: organisations, their first administrators, and emergency access.

Only platform accounts (Permission.PLATFORM_MANAGE) reach these routes, and nothing here
returns patient data: organisations are listed by name, status, and account counts. Seeing
inside an organisation takes emergency access (data/emergency.py), which is read-only,
time-limited, needs a reason, and is written to the organisation's own audit log.
"""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.data.audit import get_audit_log, get_platform_audit_log
from app.data.emergency import MAX_MINUTES, MIN_MINUTES, EmergencyAccess, get_emergency_access
from app.data.org_lifecycle import delete_organisation
from app.data.orgs import BusinessAssociateAgreement, OrgId, OrgStatus, get_org_registry
from app.data.repository import get_repository
from app.data.users import UserStore, get_user_store
from app.models import AuditEvent, Permission, Role, UserSummary
from app.models.auth import Username
from app.sample_org import empty
from app.services.auth import SessionStore, SignedIn, audit_note, get_session_store, require
from app.services.org_context import forget_organisation

router = APIRouter(
    prefix="/api/platform", tags=["platform"], dependencies=[require(Permission.PLATFORM_MANAGE)]
)

Users = Annotated[UserStore, Depends(get_user_store)]
Sessions = Annotated[SessionStore, Depends(get_session_store)]


class OrganisationInfo(BaseModel):
    id: str
    name: str
    status: OrgStatus
    created_at: datetime
    accounts: int
    active_admins: int
    baa: BusinessAssociateAgreement | None
    deleted_at: datetime | None


class OrganisationCreate(BaseModel):
    id: OrgId
    name: str = Field(min_length=2, max_length=120)


class FirstAdmin(BaseModel):
    username: Username
    display_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class BaaRecord(BaseModel):
    signed_on: date
    reference: str = Field(min_length=1, max_length=120)
    signatory: str = Field(min_length=1, max_length=120)


class DeleteRequest(BaseModel):
    confirm: str = Field(description="The organisation's ID, typed out")


class DeleteResult(BaseModel):
    organisation: "OrganisationInfo"
    done: list[str]


class EmergencyRequest(BaseModel):
    reason: str = Field(min_length=20, max_length=500, description="Why the platform needs to look")
    minutes: int = Field(default=60, ge=MIN_MINUTES, le=MAX_MINUTES)


def _info(org, users: UserStore) -> OrganisationInfo:
    members = [u for u in users.list() if u.organisation_id == org.id]
    return OrganisationInfo(
        id=org.id,
        name=org.name,
        status=org.status,
        created_at=org.created_at,
        accounts=len(members),
        active_admins=sum(1 for u in members if u.role == Role.ADMIN and u.active),
        baa=org.baa,
        deleted_at=org.deleted_at,
    )


def _org(org_id: str):
    org = get_org_registry().get(org_id)
    if org is None:
        raise HTTPException(status_code=404, detail=f"No organisation {org_id}")
    if org.status == OrgStatus.DELETED:
        raise HTTPException(status_code=409, detail=f"{org.name} was deleted")
    return org


@router.get("/organisations", response_model=list[OrganisationInfo])
def list_organisations(users: Users) -> list[OrganisationInfo]:
    return [_info(org, users) for org in get_org_registry().list()]


@router.post("/organisations", response_model=OrganisationInfo, status_code=status.HTTP_201_CREATED)
def create_organisation(body: OrganisationCreate, users: Users, request: Request) -> OrganisationInfo:
    """A new, empty organisation: the shared code sets, and its own tables waiting for its
    patients, providers, facilities, and claims to be loaded."""
    registry = get_org_registry()
    if registry.get(body.id) is not None:
        raise HTTPException(status_code=409, detail=f"Organisation {body.id} already exists")
    template = next((o for o in registry.list()), None)
    if template is None:
        raise HTTPException(status_code=409, detail="Run `python -m app.orgs migrate` first")
    audit_note(request, organisation=body.id)
    empty(registry.folder(body.id) / "data", registry.data_dir(template.id))
    org = registry.add(body.id, body.name, registry.folder(body.id).relative_to(registry.root) / "data")
    return _info(org, users)


@router.post("/organisations/{org_id}/suspend", response_model=OrganisationInfo)
def suspend_organisation(org_id: OrgId, users: Users, sessions: Sessions) -> OrganisationInfo:
    """Block every account in the organisation (signed out now); its data is kept."""
    _org(org_id)
    org = get_org_registry().set_status(org_id, OrgStatus.SUSPENDED)
    for user in users.list():
        if user.organisation_id == org_id:
            sessions.end_all(user.username)
    return _info(org, users)


@router.post("/organisations/{org_id}/reactivate", response_model=OrganisationInfo)
def reactivate_organisation(org_id: OrgId, users: Users) -> OrganisationInfo:
    _org(org_id)
    return _info(get_org_registry().set_status(org_id, OrgStatus.ACTIVE), users)


@router.post("/organisations/{org_id}/baa", response_model=OrganisationInfo)
def record_baa(
    org_id: OrgId, body: BaaRecord, users: Users, me: SignedIn, request: Request
) -> OrganisationInfo:
    """Record the organisation's signed business associate agreement. Until there is one,
    its accounts can't sign in when RCM_ENVIRONMENT=production."""
    _org(org_id)
    audit_note(request, organisation=org_id, baa_reference=body.reference)
    baa = BusinessAssociateAgreement(
        **body.model_dump(), recorded_by=me.username, recorded_at=datetime.now(UTC)
    )
    return _info(get_org_registry().set_baa(org_id, baa), users)


@router.post("/organisations/{org_id}/delete", response_model=DeleteResult)
def delete(
    org_id: OrgId, body: DeleteRequest, users: Users, me: SignedIn, request: Request
) -> DeleteResult:
    """Delete a suspended organisation for good: its data key (crypto-shredding), its
    folder, and its accounts. Export its data first if it's leaving. Can't be undone."""
    org = _org(org_id)
    if body.confirm.strip() != org_id:
        raise HTTPException(status_code=422, detail=f"Type {org_id} to confirm")
    if org.status != OrgStatus.SUSPENDED:
        raise HTTPException(status_code=409, detail="Suspend the organisation before deleting it")
    audit_note(request, organisation=org_id)
    done = delete_organisation(org_id, me.username)
    forget_organisation(org_id)
    audit_note(request, done=done)
    return DeleteResult(organisation=_info(get_org_registry().get(org_id), users), done=done)


@router.post(
    "/organisations/{org_id}/admins", response_model=UserSummary, status_code=status.HTTP_201_CREATED
)
def add_admin(org_id: OrgId, body: FirstAdmin, users: Users, request: Request) -> UserSummary:
    """An administrator for the organisation (typically its first); they manage the rest."""
    _org(org_id)
    audit_note(request, new_user=body.username)
    try:
        user = users.add(body.username, body.display_name, Role.ADMIN, body.password, org_id)
    except ValueError as err:
        code = 409 if "is taken" in str(err) else 422
        raise HTTPException(status_code=code, detail=str(err)) from err
    return UserSummary.model_validate(user.model_dump())


@router.get("/emergency-access", response_model=list[EmergencyAccess])
def list_emergency_access() -> list[EmergencyAccess]:
    """Every grant, newest first."""
    return get_emergency_access().all()


@router.post(
    "/organisations/{org_id}/emergency-access",
    response_model=EmergencyAccess,
    status_code=status.HTTP_201_CREATED,
)
def start_emergency_access(
    org_id: OrgId, body: EmergencyRequest, me: SignedIn, request: Request
) -> EmergencyAccess:
    """Read-only access to the organisation until it expires or is ended. The organisation's
    administrators see it in their audit log, with the reason, and can end it."""
    org = _org(org_id)
    if org.status != OrgStatus.ACTIVE:
        raise HTTPException(status_code=409, detail=f"{org.name} is suspended")
    grant = get_emergency_access().grant(me.username, org_id, body.reason.strip(), body.minutes)
    audit_note(request, emergency_access=grant.id, organisation=org_id)
    # Recorded in the organisation's own log, so its administrators see it
    get_audit_log(org_id).record(
        username=me.username,
        role=me.role,
        action="EMERGENCY ACCESS STARTED",
        status_code=201,
        records={"emergency_access": grant.id},
        detail={"reason": grant.reason, "until": grant.expires_at.isoformat()},
        client_ip=request.client.host if request.client else None,
    )
    get_repository(org_id)  # load its data now, so the first look isn't slow
    return grant


@router.post("/emergency-access/{grant_id}/end", response_model=EmergencyAccess)
def end_emergency_access(grant_id: str, me: SignedIn, request: Request) -> EmergencyAccess:
    grant = get_emergency_access().end(grant_id, me.username)
    if grant is None:
        raise HTTPException(status_code=404, detail=f"No emergency access {grant_id}")
    if not get_org_registry().has_data(grant.organisation_id):
        return grant  # the organisation was deleted; the platform log has this request
    get_audit_log(grant.organisation_id).record(
        username=me.username,
        role=me.role,
        action="EMERGENCY ACCESS ENDED",
        status_code=200,
        records={"emergency_access": grant.id},
        client_ip=request.client.host if request.client else None,
    )
    return grant


@router.get("/audit", response_model=list[AuditEvent])
def platform_audit(limit: int = 200) -> list[AuditEvent]:
    """Requests that belong to no organisation: platform accounts' work, unknown sign-ins."""
    return list(reversed(get_platform_audit_log().events()))[: max(1, min(limit, 1000))]
