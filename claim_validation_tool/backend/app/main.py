import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.data import get_reference_data, get_repository, get_rule_repository
from app.data.audit import get_audit_log
from app.data.users import get_user_store
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
    patients,
    payers,
    reference,
    rules,
    users,
    validation,
)
from app.services.assistant import get_retriever
from app.services.status_snapshot import get_status_snapshot

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the CSVs once at startup so the first request isn't slow
    get_repository()
    get_rule_repository()
    get_reference_data()
    get_retriever()  # knowledge base and keyword index for the assistant
    # Validate every claim up front so the first dashboard load is fast
    get_status_snapshot().get(get_repository(), get_rule_repository().list())
    if not get_user_store().list():
        logger.warning("No user accounts yet: create one with `uv run python -m app.users add`")
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
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(audit.router)
app.include_router(users.router)
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
    get_audit_log().record(
        username=username,
        role=user.role if user else None,
        action=f"{request.method} {route.path if route else request.url.path}",
        status_code=status_code,
        records=records,
        query=dict(request.query_params),
        detail={k: v for k, v in detail.items() if v is not None},
        client_ip=request.client.host if request.client else None,
    )


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "claim-validation-api",
        "version": "0.1.0",
    }
