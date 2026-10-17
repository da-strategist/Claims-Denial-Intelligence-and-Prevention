"""Accounts, roles, and the audit trail.

Each role gets the minimum it needs (HIPAA's "minimum necessary" standard): analysts see
claims and dashboards but not patient demographics, billers also work claims for named
patients, and admins also manage rules and read the audit log.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints

Username = Annotated[
    str, StringConstraints(pattern=r"^[a-z][a-z0-9._-]{2,31}$", to_lower=True, strip_whitespace=True)
]
MIN_PASSWORD_LENGTH = 12


class Role(StrEnum):
    ANALYST = "analyst"
    BILLER = "biller"
    ADMIN = "admin"


class Permission(StrEnum):
    CLAIMS_READ = "claims:read"  # claims, validation, AI Fix suggestions, dashboard, assistant
    PATIENTS_READ = "patients:read"  # names and demographics; patient search
    CLAIMS_WRITE = "claims:write"  # enter and submit claims, apply and undo fixes
    RULES_WRITE = "rules:write"  # create, edit, test, and delete validation rules
    AUDIT_READ = "audit:read"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ANALYST: frozenset({Permission.CLAIMS_READ}),
    Role.BILLER: frozenset(
        {Permission.CLAIMS_READ, Permission.PATIENTS_READ, Permission.CLAIMS_WRITE}
    ),
    Role.ADMIN: frozenset(Permission),
}


class User(BaseModel):
    """A stored account. `password_hash` never leaves the server."""

    username: Username
    display_name: str = Field(min_length=1, max_length=80)
    role: Role
    password_hash: str
    active: bool = True
    created_at: datetime
    password_changed_at: datetime

    @property
    def permissions(self) -> frozenset[Permission]:
        return ROLE_PERMISSIONS[self.role]

    def can(self, permission: Permission) -> bool:
        return permission in self.permissions


class CurrentUser(BaseModel):
    """The signed-in user, as the frontend sees them."""

    username: str
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
