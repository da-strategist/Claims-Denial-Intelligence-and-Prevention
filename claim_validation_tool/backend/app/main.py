from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.data import get_reference_data, get_repository, get_rule_repository
from app.routers import aifix, claims, dashboard, departments, jab, payers, rules, validation
from app.services.status_snapshot import get_status_snapshot


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the CSVs once at startup so the first request isn't slow
    get_repository()
    get_rule_repository()
    get_reference_data()
    # Validate every claim up front so the first dashboard load is fast
    get_status_snapshot().get(get_repository(), get_rule_repository().list())
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

app.include_router(claims.router)
app.include_router(payers.router)
app.include_router(departments.router)
app.include_router(rules.router)
app.include_router(validation.router)
app.include_router(aifix.router)
app.include_router(dashboard.router)
app.include_router(jab.router)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "claim-validation-api",
        "version": "0.1.0",
    }
