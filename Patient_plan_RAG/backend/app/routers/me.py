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
from ..services import accounts, records, registry
from ..services import sharing as sharing_service

router = APIRouter(prefix="/api/me", tags=["me"])

_own = require(Permission.MANAGE_OWN_DATA)
PROVIDER_KINDS = ("doctor", "hospital", "clinic", "pharmacy", "laboratory", "imaging", "dental", "other")
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
    return [{"org_id": org_id, "org_name": names.get(org_id, "Unknown provider"), "policies": docs}
            for org_id, docs in sorted(by_org.items(), key=lambda kv: names.get(kv[0], ""))]


def _provider_row(p: records.Provider) -> dict:
    """An entry in the individual's list; linked ones carry the platform
    provider's current details. The provider's own patient record ID stays
    with the provider."""
    row = {k: v for k, v in vars(p).items() if k != "patient_id"}
    org = records.orgs.get(p.org_id) if p.org_id else None
    row["on_platform"] = bool(org and org.usable)
    if org:
        row |= {"name": org.name, "city": org.city,
                "category_label": records.PROVIDER_CATEGORIES.get(org.category, org.category)}
    return row


def _providers(user: User) -> list[dict]:
    return [_provider_row(p) for p in sorted(records.providers.all(), key=lambda p: p.name.lower())
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
    updated = user_store.update(user.username, full_name=body.full_name.strip(),
                                phone=body.phone.strip())
    sharing_service.refresh_names(user.username)  # provider records still named after the email
    return updated.public()


@router.post("/sign-out-everywhere")
async def sign_out_everywhere(response: Response, user: User = Depends(signed_in)) -> dict:
    """End every session for this account, including this one."""
    sessions.end_all_for(user.username)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"signed_out": True}


# ── Providers ────────────────────────────────────────────────────────

class ProviderIn(BaseModel):
    """Typed in by hand (`name` required), or a provider on the platform
    (`org_id`; its name and category are used)."""
    name: str = Field("", max_length=120)
    kind: str = Field("doctor", pattern="^(" + "|".join(PROVIDER_KINDS) + ")$")
    phone: str = Field("", max_length=30, pattern=r"^[0-9 +().-]*$")
    notes: str = Field("", max_length=500)
    org_id: str | None = Field(None, pattern=DOCUMENT_ID_PATTERN)


def _platform_provider_or_404(user: User, org_id: str, provider_id: str | None = None) -> records.Org:
    org = records.orgs.get(org_id)
    if org is None or not org.usable:
        raise HTTPException(404, "Provider not found")
    linked = records.connection(user.username, org_id)
    if linked and linked.provider_id != provider_id:
        raise HTTPException(400, f"{org.name} is already in your providers.")
    return org


def _kind_for(org: records.Org) -> str:
    return org.category if org.category in PROVIDER_KINDS else "other"


def _now() -> str:
    return datetime.now(UTC).isoformat()


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
    """Add a provider. Choosing one on the platform connects you: it sees your
    name and email (no policies — share those separately)."""
    if body.org_id:
        org = _platform_provider_or_404(user, body.org_id)
        p = records.Provider(records.new_id(), user.username, org.name, _kind_for(org),
                             body.phone.strip(), body.notes.strip(), org_id=org.org_id,
                             connected_at=_now())
    else:
        if not body.name.strip():
            raise HTTPException(400, "Enter the provider's name.")
        p = records.Provider(records.new_id(), user.username, body.name.strip(), body.kind,
                             body.phone.strip(), body.notes.strip())
    return _provider_row(records.providers.add(p))


@router.patch("/providers/{provider_id}")
async def update_provider(body: ProviderIn, provider_id: str = ProviderIdParam,
                          user: User = Depends(_own)) -> dict:
    """Edit phone/notes (and name/type of a hand-typed entry), or link a
    hand-typed entry to a provider on the platform (`org_id`)."""
    p = _own_provider_or_404(user, provider_id)
    changes = {"phone": body.phone.strip(), "notes": body.notes.strip()}
    if body.org_id and body.org_id != p.org_id:
        org = _platform_provider_or_404(user, body.org_id, provider_id)
        changes |= {"org_id": org.org_id, "name": org.name, "kind": _kind_for(org),
                    "patient_id": None, "connected_at": _now()}
    elif not p.org_id:
        if not body.name.strip():
            raise HTTPException(400, "Enter the provider's name.")
        changes |= {"name": body.name.strip(), "kind": body.kind}
    return _provider_row(records.providers.update(provider_id, **changes))


@router.delete("/providers/{provider_id}")
async def delete_provider(provider_id: str = ProviderIdParam, user: User = Depends(_own)) -> dict:
    """Remove a provider (and the connection, if it's on the platform).
    Policies shared with it stay shared until you stop sharing them."""
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
        raise HTTPException(404, "That provider has no access to your policies")
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
    accounts.delete_individual(user.username, policies.CHUNK_DIR, policies.UPLOAD_DIR)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"deleted": user.username}
