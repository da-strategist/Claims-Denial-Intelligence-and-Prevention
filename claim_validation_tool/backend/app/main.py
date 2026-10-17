import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.data import get_reference_data, get_repository, get_rule_repository
from app.data.audit import AuditLog, get_audit_log, get_platform_audit_log
from app.data.orgs import OrgStatus, get_org_registry
from app.data.secure_files import MASTER_KEY_ENV, master_key, production
from app.data.users import get_user_store
from app.services.auth import cookie_secure
from app.models import Role
from app.routers import (
    aifix,
    assistant,
    audit,
    auth,
    claims,
    dashboard,
    departments,
    drafts,
    jab,
    organisation,
    patients,
    payers,
    reference,
    rules,
    platform,
    users,
    validation,
)
from app.services.assistant import get_retriever
from app.services.status_snapshot import get_status_snapshot

logger = logging.getLogger("uvicorn.error")


def allowed_origins() -> list[str]:
    """Web addresses the app is served from (RCM_ALLOWED_ORIGINS, comma-separated)."""
    raw = os.environ.get("RCM_ALLOWED_ORIGINS", "http://localhost:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    if master_key() is None:
        if production():
            # Patient data is never written unencrypted in production
            raise RuntimeError(f"RCM_ENVIRONMENT=production needs {MASTER_KEY_ENV} (encryption at rest)")
        logger.warning(f"{MASTER_KEY_ENV} isn't set: organisations' data is saved unencrypted")
    if production() and not cookie_secure():
        raise RuntimeError("RCM_ENVIRONMENT=production needs RCM_COOKIE_SECURE=1 (HTTPS only)")
    if production():
        for org in get_org_registry().list():
            if org.status == OrgStatus.ACTIVE and org.baa is None:
                logger.warning(f"{org.id} has no business associate agreement on record: its accounts can't sign in")
    # Load each organisation's data once at startup so the first request isn't slow
    orgs = [org for org in get_org_registry().list() if org.status == OrgStatus.ACTIVE]
    if not orgs:
        logger.warning("No organisations yet: run `uv run python -m app.orgs migrate`")
    for org in orgs:
        repo, rules = get_repository(org.id), get_rule_repository(org.id)
        get_reference_data(org.id)
        get_retriever(org.id)  # knowledge base and keyword index for the assistant
        # Validate every claim up front so the first dashboard load is fast
        get_status_snapshot(org.id).get(repo, rules.list())
    users = get_user_store().list()
    if not users:
        logger.warning("No user accounts yet: create one with `uv run python -m app.users add`")
    if any(user.organisation_id is None and user.role != Role.PLATFORM for user in users):
        logger.warning(
            "Some accounts have no organisation and can't sign in: run `uv run python -m app.orgs migrate`"
        )
    yield


app = FastAPI(
    title="ClaustraRCM Claim Validation API",
    version="0.1.0",
    description="AI-Powered Claims Denial Intelligence & Prevention",
    lifespan=lifespan,
)

# Allow React dev server to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(audit.router)
app.include_router(users.router)
app.include_router(organisation.router)
app.include_router(platform.router)
app.include_router(claims.router)
app.include_router(drafts.router)
app.include_router(payers.router)
app.include_router(departments.router)
app.include_router(rules.router)
app.include_router(validation.router)
app.include_router(aifix.router)
app.include_router(dashboard.router)
app.include_router(jab.router)
app.include_router(patients.router)
app.include_router(reference.router)
app.include_router(assistant.router)


# Not audited: the health check, and the browser's CORS preflight requests
UNAUDITED_PATHS = {"/api/health"}


@app.middleware("http")
async def audit_requests(request: Request, call_next):
    """Record every API request in the audit log: who, what, which records, and the outcome."""
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        path = request.url.path
        if path.startswith("/api/") and path not in UNAUDITED_PATHS and request.method != "OPTIONS":
            _audit(request, status_code)


def _audit(request: Request, status_code: int) -> None:
    user = getattr(request.state, "user", None)
    detail = dict(getattr(request.state, "audit", {}))
    route = request.scope.get("route")
    records = {k: str(v) for k, v in request.scope.get("path_params", {}).items()}
    # Record IDs noted by the route (e.g. the claim a new claim was entered as)
    for key in ("claim_id", "patient_id", "draft_id"):
        if detail.get(key):
            records[key] = str(detail.pop(key))
    username = user.username if user else detail.pop("attempted_username", None)
    if user is not None and user.emergency_access_id:
        detail["emergency_access"] = user.emergency_access_id
    platform_route = request.url.path.startswith("/api/platform/")
    log = get_platform_audit_log() if platform_route else _audit_log_for(user, username)
    log.record(
        username=username,
        role=user.role if user else None,
        action=f"{request.method} {route.path if route else request.url.path}",
        status_code=status_code,
        records=records,
        query=dict(request.query_params),
        detail={k: v for k, v in detail.items() if v is not None},
        client_ip=request.client.host if request.client else None,
    )


def _audit_log_for(user, username: str | None) -> AuditLog:
    """The organisation's own log for its users' requests (including failed sign-ins to its
    accounts); the platform log for requests that belong to no organisation."""
    account = user or (get_user_store().get(username) if username else None)
    org_id = account.organisation_id if account else None
    if org_id and get_org_registry().has_data(org_id):
        return get_audit_log(org_id)
    return get_platform_audit_log()


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "claim-validation-api",
        "version": "0.1.0",
    }
