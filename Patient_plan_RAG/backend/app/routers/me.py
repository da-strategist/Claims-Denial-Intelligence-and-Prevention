"""The signed-in individual's own account: profile, insurance overview,
providers, who can see their policies, export, and account deletion."""

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi import Path as PathParam
from pydantic import BaseModel, Field

from ..audit import audit_target
from ..auth.sessions import SESSION_COOKIE, Permission, require, sessions, signed_in
from ..auth.users import User, user_store
from ..models.common import DISCLAIMER, DOCUMENT_ID_PATTERN
from ..services import documents, records, registry

router = APIRouter(prefix="/api/me", tags=["me"])

_own = require(Permission.MANAGE_OWN_DATA)
PROVIDER_KINDS = ("doctor", "hospital", "clinic", "pharmacy", "other")
ProviderIdParam = PathParam(pattern=DOCUMENT_ID_PATTERN)
OrgIdParam = PathParam(pattern=DOCUMENT_ID_PATTERN)


def _own_documents(user: User) -> list[dict]:
    return [e for e in registry.load() if e.get("owner") == user.username]


def _label(e: dict) -> str:
    return e.get("display_name") or e.get("plan_name") or e["filename"]


# ── Overview (the individual's home page) ────────────────────────────

def _insurance(user: User) -> list[dict]:
    """The user's policies grouped by insurance company."""
    today = date.today().isoformat()
    groups: dict[str, list[dict]] = {}
    for e in _own_documents(user):
        expires = e.get("expiration_date") or ""
        groups.setdefault(e.get("insurer_name") or "Insurer not stated", []).append({
            "document_id": e["document_id"], "name": _label(e),
            "plan_name": e.get("plan_name", ""), "plan_id": e.get("plan_id", ""),
            "effective_date": e.get("effective_date"), "expiration_date": e.get("expiration_date"),
            "expired": bool(expires) and expires < today,
        })
    return [{"insurer": k, "plans": v} for k, v in sorted(groups.items())]


def _sharing(user: User) -> list[dict]:
    """Hospitals that can see the user's policies, with which ones."""
    names = {o.org_id: o.name for o in records.orgs.all()}
    labels = {e["document_id"]: _label(e) for e in _own_documents(user)}
    by_org: dict[str, list[dict]] = {}
    for s in records.shares.all():
        if s.shared_by == user.username and s.document_id in labels:
            by_org.setdefault(s.org_id, []).append(
                {"share_id": s.share_id, "document_id": s.document_id, "name": labels[s.document_id]})
    return [{"org_id": org_id, "org_name": names.get(org_id, "Unknown hospital"), "policies": docs}
            for org_id, docs in sorted(by_org.items(), key=lambda kv: names.get(kv[0], ""))]


def _providers(user: User) -> list[dict]:
    return [vars(p) for p in sorted(records.providers.all(), key=lambda p: p.name.lower())
            if p.owner == user.username]


@router.get("/overview")
async def overview(user: User = Depends(_own)) -> dict:
    return {
        "profile": user.public(),
        "insurance": _insurance(user),
        "providers": _providers(user),
        "sharing": _sharing(user),
        "policy_count": len(_own_documents(user)),
        "disclaimer": DISCLAIMER,
    }


# ── Profile (any signed-in user) ─────────────────────────────────────

class ProfileChanges(BaseModel):
    full_name: str = Field("", max_length=120)
    phone: str = Field("", max_length=30, pattern=r"^[0-9 +().-]*$")


@router.patch("/profile")
async def update_profile(body: ProfileChanges, user: User = Depends(signed_in)) -> dict:
    return user_store.update(user.username, full_name=body.full_name.strip(),
                             phone=body.phone.strip()).public()


@router.post("/sign-out-everywhere")
async def sign_out_everywhere(response: Response, user: User = Depends(signed_in)) -> dict:
    """End every session for this account, including this one."""
    sessions.end_all_for(user.username)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"signed_out": True}


# ── Providers ────────────────────────────────────────────────────────

class ProviderIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field("doctor", pattern="^(" + "|".join(PROVIDER_KINDS) + ")$")
    phone: str = Field("", max_length=30, pattern=r"^[0-9 +().-]*$")
    notes: str = Field("", max_length=500)


def _own_provider_or_404(user: User, provider_id: str) -> records.Provider:
    p = records.providers.get(provider_id)
    if p is None or p.owner != user.username:
        raise HTTPException(404, "Provider not found")
    return p


@router.get("/providers")
async def list_providers(user: User = Depends(_own)) -> list[dict]:
    return _providers(user)


@router.post("/providers")
async def add_provider(body: ProviderIn, user: User = Depends(_own)) -> dict:
    p = records.providers.add(records.Provider(
        records.new_id(), user.username, body.name.strip(), body.kind,
        body.phone.strip(), body.notes.strip()))
    return vars(p)


@router.patch("/providers/{provider_id}")
async def update_provider(body: ProviderIn, provider_id: str = ProviderIdParam,
                          user: User = Depends(_own)) -> dict:
    _own_provider_or_404(user, provider_id)
    return vars(records.providers.update(provider_id, name=body.name.strip(), kind=body.kind,
                                         phone=body.phone.strip(), notes=body.notes.strip()))


@router.delete("/providers/{provider_id}")
async def delete_provider(provider_id: str = ProviderIdParam, user: User = Depends(_own)) -> dict:
    _own_provider_or_404(user, provider_id)
    records.providers.remove(provider_id)
    return {"deleted": provider_id}


# ── Who can see my policies ──────────────────────────────────────────

@router.get("/sharing")
async def sharing(user: User = Depends(_own)) -> list[dict]:
    return _sharing(user)


@router.delete("/sharing/{org_id}")
async def remove_hospital_access(org_id: str = OrgIdParam,
                                 user: User = Depends(_own)) -> dict:
    """Stop sharing every policy with one hospital."""
    removed = 0
    for s in records.shares.all():
        if s.shared_by == user.username and s.org_id == org_id:
            records.shares.remove(s.share_id)
            removed += 1
    if not removed:
        raise HTTPException(404, "That hospital has no access to your policies")
    return {"org_id": org_id, "revoked": removed}


# ── Export and deletion ──────────────────────────────────────────────

@router.get("/export")
async def export(user: User = Depends(_own)) -> dict:
    """Everything this platform holds about you, as JSON (policy PDFs can be
    downloaded from their pages)."""
    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "profile": user.public(),
        "policies": [{k: e.get(k) for k in (
            "document_id", "filename", "display_name", "insurer_name", "plan_name", "plan_id",
            "effective_date", "expiration_date", "page_count", "status")}
            for e in _own_documents(user)],
        "providers": _providers(user),
        "sharing": _sharing(user),
    }


class DeleteAccount(BaseModel):
    confirm_email: str = Field(min_length=3, max_length=254)


@router.delete("")
async def delete_account(body: DeleteAccount, request: Request, response: Response,
                         user: User = Depends(_own)) -> dict:
    """Delete the account: policies (files, search index, shares — hospitals
    lose access at once), providers and profile. The audit log keeps its
    past entries (it is append-only) and records this deletion."""
    if body.confirm_email.strip().lower() != user.username:
        raise HTTPException(400, "Type your email address exactly to confirm")
    from . import policies  # paths are read at call time so tests can redirect them

    audit_target(request, user.username)
    for entry in _own_documents(user):
        documents.delete(entry, policies.CHUNK_DIR, policies.UPLOAD_DIR)
    for s in records.shares.all():
        if s.shared_by == user.username:
            records.shares.remove(s.share_id)
    for p in records.providers.all():
        if p.owner == user.username:
            records.providers.remove(p.provider_id)
    sessions.end_all_for(user.username)
    user_store.delete(user.username)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"deleted": user.username}
