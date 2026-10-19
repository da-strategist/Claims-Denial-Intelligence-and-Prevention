"""FastAPI application entry point for Patient Plan RAG."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import chat, coverage, dashboard, policies

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
    """Pre-load synthetic policies on startup."""
    from .services.document_processor import process_document
    import hashlib
    import json

    # Process any pre-loaded synthetic policy PDFs. IDs are derived from file
    # content so rebuilding the registry overwrites chunk files, not orphans them.
    registry_path = POLICY_DIR / "_registry.json"
    if not registry_path.exists():
        registry: list[dict] = []
        for pdf in sorted(POLICY_DIR.glob("*.pdf")):
            content_id = hashlib.sha256(pdf.read_bytes()).hexdigest()[:12]
            doc, chunks = process_document(pdf, CHUNK_DIR, document_id=content_id)
            registry.append(doc.model_dump(mode="json"))
        registry_path.write_text(json.dumps(registry, indent=2, default=str))

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

# CORS
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(policies.router)
app.include_router(chat.router)
app.include_router(coverage.router)
app.include_router(dashboard.router)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "mode": os.getenv("APP_MODE", "demo"),
        "disclaimer": (
            "This tool provides AI-generated interpretations of insurance "
            "policy language. It does not constitute coverage determinations, "
            "legal advice, or guarantees of benefits."
        ),
    }
