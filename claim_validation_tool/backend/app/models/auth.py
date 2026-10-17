"""Accounts, roles, and the audit trail.

Each role gets the minimum it needs (HIPAA's "minimum necessary" standard): analysts see
claims and dashboards but not patient demographics, billers also work claims for named
patients, and admins also manage rules, user accounts, and read the audit log.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints

from app.models.common import DepartmentId, FacilityId, ProviderId

Username = Annotated[
    str, StringConstraints(pattern=r"^[a-z][a-z0-9._-]{2,31}$", to_lower=True, strip_whitespace=True)
]
MIN_PASSWORD_LENGTH = 12


class Role(StrEnum):
    ANALYST = "analyst"
    BILLER = "biller"
    ADMIN = "admin"
    # Runs the hosted service: manages organisations, belongs to none, sees no patient
    # data except through audited, read-only, time-limited emergency access
    PLATFORM = "platform"


# Roles an organisation's administrators can give (never platform)
ORGANISATION_ROLES = (Role.ANALYST, Role.BILLER, Role.ADMIN)


class Permission(StrEnum):
    CLAIMS_READ = "claims:read"  # claims, validation, AI Fix suggestions, dashboard, assistant
    PATIENTS_READ = "patients:read"  # names and demographics; patient search
    CLAIMS_WRITE = "claims:write"  # enter and submit claims, apply and undo fixes
    RULES_WRITE = "rules:write"  # create, edit, test, and delete validation rules
    AUDIT_READ = "audit:read"
    USERS_MANAGE = "users:manage"  # create accounts, change roles, reset passwords, disable
    DATA_EXPORT = "data:export"  # download all the organisation's data
    PLATFORM_MANAGE = "platform:manage"  # organisations, their first admins, emergency access


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ANALYST: frozenset({Permission.CLAIMS_READ}),
    Role.BILLER: frozenset(
        {Permission.CLAIMS_READ, Permission.PATIENTS_READ, Permission.CLAIMS_WRITE}
    ),
    Role.ADMIN: frozenset(Permission) - {Permission.PLATFORM_MANAGE},
    Role.PLATFORM: frozenset({Permission.PLATFORM_MANAGE}),
}

# What emergency access lets a platform account do inside an organisation: look, never change
EMERGENCY_PERMISSIONS = frozenset({Permission.CLAIMS_READ, Permission.PATIENTS_READ})


class AccessScope(BaseModel):
    """The part of the organisation an account may see (need to know). Empty everywhere
    means the whole organisation, the default. Otherwise a claim is visible when it matches
    ANY of the limits: its facility, its department, or its provider. Administrators are
    always organisation-wide."""

    facilities: list[FacilityId] = Field(default_factory=list, max_length=50)
    departments: list[DepartmentId] = Field(default_factory=list, max_length=50)
    providers: list[ProviderId] = Field(default_factory=list, max_length=200)

    @property
    def restricted(self) -> bool:
        return bool(self.facilities or self.departments or self.providers)

    def allows(self, facility_id: str | None, department_id: str | None, provider_id: str | None) -> bool:
        return (
            not self.restricted
            or facility_id in self.facilities
            or department_id in self.departments
            or provider_id in self.providers
        )


class User(BaseModel):
    """A stored account. `password_hash` never leaves the server."""

    username: Username
    display_name: str = Field(min_length=1, max_length=80)
    role: Role
    password_hash: str
    active: bool = True
    created_at: datetime
    password_changed_at: datetime
    # The one organisation whose data this account can reach. None (an account from before
    # organisations) can't sign in until `python -m app.orgs migrate` assigns one.
    organisation_id: str | None = None
    scope: AccessScope = Field(default_factory=AccessScope)
    # Set per request (never stored) while a platform account uses emergency access
    emergency_access_id: str | None = Field(default=None, exclude=True)

    @property
    def effective_scope(self) -> AccessScope:
        """Administrators always see the whole organisation."""
        return AccessScope() if self.role == Role.ADMIN else self.scope

    @property
    def permissions(self) -> frozenset[Permission]:
        if self.emergency_access_id is not None:
            # Look inside the organisation, and still manage the platform (e.g. end access)
            return EMERGENCY_PERMISSIONS | ROLE_PERMISSIONS[self.role]
        return ROLE_PERMISSIONS[self.role]

    def can(self, permission: Permission) -> bool:
        return permission in self.permissions


class UserSummary(BaseModel):
    """An account as the Users page shows it (never the password hash)."""

    username: str
    display_name: str
    role: Role
    active: bool
    created_at: datetime
    password_changed_at: datetime
    scope: AccessScope


class UserCreate(BaseModel):
    username: Username
    display_name: Annotated[str, StringConstraints(min_length=1, max_length=80, strip_whitespace=True)]
    role: Role
    password: str = Field(min_length=1, max_length=256)


class UserUpdate(BaseModel):
    """Fields to change; omitted ones stay as they are."""

    display_name: Annotated[
        str, StringConstraints(min_length=1, max_length=80, strip_whitespace=True)
    ] | None = None
    role: Role | None = None
    active: bool | None = None
    scope: AccessScope | None = Field(
        default=None, description="Limit what the account sees; empty lists = whole organisation"
    )


class PasswordReset(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class OrganisationSummary(BaseModel):
    id: str
    name: str


class EmergencySummary(BaseModel):
    """A platform account's current emergency access, for the banner it works under."""

    id: str
    reason: str
    expires_at: datetime


class CurrentUser(BaseModel):
    """The signed-in user, as the frontend sees them."""

    username: str
    organisation: OrganisationSummary | None = Field(
        description="None for a platform account outside emergency access"
    )
    emergency: EmergencySummary | None = None
    access: str | None = Field(
        default=None, description="What a limited account sees, e.g. 'Cardiology · Dr. Robinson'"
    )
    display_name: str
    role: Role
    permissions: list[Permission]
    session_expires_at: datetime = Field(description="Absolute end of this session")
    idle_timeout_minutes: int = Field(description="Signed out after this long without a request")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class AuditOutcome(StrEnum):
    SUCCESS = "success"
    DENIED = "denied"  # not signed in, or the role lacks the permission
    FAILED = "failed"  # rejected input, not found, or a server error


class AuditEvent(BaseModel):
    """One API request: who did what to which record, when, and whether it worked.

    Events form a hash chain (`hash` covers the event and the previous event's hash), so an
    edited or deleted line breaks verification from that point on.
    """

    seq: int = Field(ge=1)
    at: datetime
    username: str | None = Field(description="Signed-in user, or the name tried at login")
    role: Role | None
    action: str = Field(description='Method and route, e.g. "POST /api/aifix/{claim_id}/apply"')
    records: dict[str, str] = Field(
        default_factory=dict, description="IDs of the records involved, e.g. claim_id"
    )
    query: dict[str, str] = Field(default_factory=dict, description="Search and filter parameters")
    detail: dict[str, Any] = Field(default_factory=dict)
    status_code: int
    outcome: AuditOutcome
    client_ip: str | None
    prev_hash: str
    hash: str


class AuditQuery(BaseModel):
    username: str | None = None
    record_id: str | None = Field(default=None, description="Any record ID, e.g. CLM0000001")
    outcome: AuditOutcome | None = None
    limit: int = Field(default=200, ge=1, le=1000)


class AuditVerification(BaseModel):
    ok: bool
    events: int
    first_bad_seq: int | None = Field(
        default=None, description="First event whose hash doesn't match (edited or removed)"
    )
