"""FastAPI application entry point for Patient Plan RAG."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import audit
from .models.common import DISCLAIMER
from .rate_limit import api_limiter, upload_limiter
from .routers import admin, auth, chat, coverage, dashboard, hospital, me, policies, shares

# ── Directories ──────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "data" / "uploads")))
POLICY_DIR = Path(os.getenv("POLICY_DIR", str(BASE_DIR / "data" / "policies")))
CHUNK_DIR = Path(os.getenv("CHUNK_DIR", str(BASE_DIR / "data" / "chunks")))

for d in (UPLOAD_DIR, POLICY_DIR, CHUNK_DIR):
    d.mkdir(parents=True, exist_ok=True)


# ── Lifespan ─────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ingest new PDFs and re-ingest stale documents before serving."""
    from .services import sharing
    from .services.ingest import sync_registry

    sync_registry(POLICY_DIR, UPLOAD_DIR, CHUNK_DIR)
    sharing.backfill()  # patient records for shares made before they were automatic
    yield


# ── App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Patient Plan RAG",
    description=(
        "AI-Powered Health Insurance Coverage & Prior Authorization Assistant. "
        "⚠️ For demonstration purposes only — not a substitute for professional "
        "insurance or medical advice."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    """Per-client request limits on the API (health checks exempt)."""
    path = request.url.path
    if path.startswith("/api") and path != "/api/health":
        client = request.client.host if request.client else "unknown"
        strict = path in ("/api/policies/upload", "/api/auth/register", "/api/auth/register/provider")
        limiter = upload_limiter if strict else api_limiter
        wait = limiter.check(client)
        if wait is not None:
            return JSONResponse(
                {"detail": "Too many requests, please slow down."},
                status_code=429,
                headers={"Retry-After": str(max(1, round(wait)))},
            )
    return await call_next(request)


_ALLOWED_ORIGINS = {
    o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5174,http://127.0.0.1:5174").split(",")
}


@app.middleware("http")
async def check_origin(request: Request, call_next):
    """Reject state-changing requests sent from other sites (CSRF defence in
    depth on top of SameSite=Strict cookies; uploads are form posts, which
    any site can submit). Requests without an Origin header are allowed."""
    origin = request.headers.get("origin")
    if (request.method in ("POST", "PUT", "PATCH", "DELETE")
            and request.url.path.startswith("/api") and origin
            and origin not in _ALLOWED_ORIGINS):
        return JSONResponse({"detail": "Cross-site request refused"}, status_code=403)
    return await call_next(request)


# Registered after rate_limit, so it wraps it and 429s carry the header too.
@app.middleware("http")
async def add_disclaimer_header(request: Request, call_next):
    """Every API response carries the disclaimer, including list endpoints."""
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        response.headers["X-Disclaimer"] = DISCLAIMER
    return response


@app.middleware("http")
async def audit_access(request: Request, call_next):
    """Record every API request (identity and target, never content) in the
    hash-chained audit log. Registered after the other middleware so refused
    requests (403/429) are recorded too. A failed write fails the request."""
    response = await call_next(request)
    if request.url.path.startswith("/api") and request.url.path != "/api/health":
        audit.record(audit.entry_for(request, response.status_code))
    return response


# CORS — added last so it is outermost and error responses get CORS headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(_ALLOWED_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Disclaimer"],
)


# Routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(hospital.router)
app.include_router(shares.router)
app.include_router(me.router)
app.include_router(policies.router)
app.include_router(chat.router)
app.include_router(coverage.router)
app.include_router(dashboard.router)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "mode": os.getenv("APP_MODE", "demo"),
        "disclaimer": DISCLAIMER,
    }
