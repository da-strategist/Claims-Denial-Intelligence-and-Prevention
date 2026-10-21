"""Platform oversight for the platform admin: usage dashboard, the audit log,
security events, and the health of the sample policies.

Everything here is counts and metadata. The audit log never holds request
bodies, questions or answers, so none of these views can show them.
"""

import json
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as PathParam

from .. import audit
from ..auth.access import is_sample
from ..auth.sessions import Permission, require
from ..auth.users import HOSPITAL_ROLES, Role, User, user_store
from ..models.common import DOCUMENT_ID_PATTERN
from ..services import ingest, records, registry
from ..services.document_processor import CHUNKER_VERSION

router = APIRouter(prefix="/api/admin", tags=["oversight"])

_oversee = require(Permission.MANAGE_USERS)
WEEKS = 8
# successful requests counted as platform activity: label -> (method, route)
ACTIVITY = {
    "sign_ins": ("POST", "/api/auth/login"),
    "questions": ("POST", "/api/chat"),
    "coverage_checks": ("POST", "/api/coverage/assess"),
    "prior_auth_checklists": ("POST", "/api/coverage/auth-checklist"),
    "uploads": ("POST", "/api/policies/upload"),
    "shares": ("POST", "/api/shares"),
}
METADATA_FIELDS = ("insurer_name", "plan_name", "plan_id", "effective_date", "expiration_date")


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _weeks() -> list[str]:
    this = _week_start(datetime.now(UTC).date())
    return [(this - timedelta(weeks=n)).isoformat() for n in range(WEEKS - 1, -1, -1)]


def _week_of(iso: str) -> str | None:
    try:
        return _week_start(datetime.fromisoformat(iso).date()).isoformat()
    except (TypeError, ValueError):
        return None


def _per_week(timestamps) -> list[int]:
    counts = Counter(_week_of(t) for t in timestamps)
    return [counts.get(w, 0) for w in _weeks()]


# ── Dashboard ────────────────────────────────────────────────────────

@router.get("/stats")
async def stats(_: User = Depends(_oversee)) -> dict:
    users, orgs, entries = user_store.all(), records.orgs.all(), audit.read_entries()
    docs = registry.load()
    ok = [e for e in entries if 200 <= (e.get("status") or 0) < 300]
    return {
        "weeks": _weeks(),
        "accounts": {
            "individuals": sum(u.role is Role.INDIVIDUAL for u in users),
            "provider_staff": sum(u.role in HOSPITAL_ROLES for u in users),
            "platform_admins": sum(u.role is Role.PLATFORM_ADMIN for u in users),
            "disabled": sum(u.disabled for u in users),
        },
        "providers": {
            "by_status": dict(Counter("disabled" if o.disabled else o.status for o in orgs)),
            "by_category": dict(Counter(records.PROVIDER_CATEGORIES.get(o.category, o.category)
                                        for o in orgs if o.usable)),
        },
        "sign_ups": {
            "individuals": _per_week(u.created_at for u in users if u.role is Role.INDIVIDUAL),
            "providers": _per_week(o.created_at for o in orgs),
        },
        "activity": {label: _per_week(e["ts"] for e in ok
                                      if (e.get("method"), e.get("route")) == key)
                     for label, key in ACTIVITY.items()},
        "totals": {
            "individual_policies": sum(1 for d in docs if d.get("owner")),
            "provider_uploads": sum(1 for d in docs if d.get("org_id")),
            "samples": sum(1 for d in docs if is_sample(d)),
            "shares": len(records.shares.all()),
            "connections": sum(1 for p in records.providers.all() if p.org_id),
            "patient_records": len(records.patients.all()),
        },
    }


# ── Audit log ────────────────────────────────────────────────────────

@router.get("/audit")
async def audit_log(
    user: str = Query("", max_length=254),
    route: str = Query("", max_length=200),
    status: str = Query("", pattern=r"^(|2xx|4xx|5xx|\d{3})$"),
    org_id: str = Query("", pattern=r"^([A-Za-z0-9_-]{1,64})?$"),
    since: str = Query("", pattern=r"^(\d{4}-\d{2}-\d{2})?$"),
    until: str = Query("", pattern=r"^(\d{4}-\d{2}-\d{2})?$"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    include_routine: bool = Query(False),
    _: User = Depends(_oversee),
) -> dict:
    """The audit log, newest first, filtered, with a plain-words label per
    entry. Routine page loads are left out unless `include_routine`.
    Entries hold who, what route, which document/patient/account, status and
    client — never content."""
    staff = {u.username for u in user_store.all() if u.org_id == org_id} if org_id else None

    def keep(e: dict) -> bool:
        code = str(e.get("status") or "")
        return ((not user or user.lower() in (e.get("user") or "").lower())
                and (not route or route in (e.get("route") or ""))
                and (not status or (code[0] + "xx" == status if status.endswith("xx") else code == status))
                and (staff is None or e.get("user") in staff)
                and (not since or e.get("ts", "") >= since)
                and (not until or e.get("ts", "")[:10] <= until))

    rows = []
    for e in reversed(audit.read_entries()):
        label, routine = audit.describe(e)
        if keep(e) and (include_routine or not routine):
            rows.append((e, label, routine))
    fields = ("ts", "user", "role", "method", "route", "document_id", "patient_id", "target",
              "status", "client")
    return {"total": len(rows),
            "entries": [{k: e.get(k) for k in fields} | {"label": label, "routine": routine}
                        for e, label, routine in rows[offset:offset + limit]]}


@router.get("/audit/verify")
async def verify_audit(_: User = Depends(_oversee)) -> dict:
    """Check the hash chain: any edited, inserted or deleted line breaks it."""
    ok, lines, problem = audit.verify()
    return {"ok": ok, "lines": lines, "problem": problem}


# ── Security events ──────────────────────────────────────────────────

def _group(entries: list[dict]) -> list[dict]:
    by_user: dict[str, dict] = defaultdict(lambda: {"count": 0, "last": "", "clients": set()})
    for e in entries:
        g = by_user[e.get("user") or "(unknown)"]
        g["count"] += 1
        g["last"] = max(g["last"], e.get("ts", ""))
        if e.get("client"):
            g["clients"].add(e["client"])
    rows = [{"user": u, "count": g["count"], "last": g["last"], "clients": sorted(g["clients"])}
            for u, g in by_user.items()]
    return sorted(rows, key=lambda r: (-r["count"], r["user"]))


@router.get("/security")
async def security_events(days: int = Query(7, ge=1, le=90), _: User = Depends(_oversee)) -> dict:
    """Failed and locked-out sign-ins, refused requests (403/404) and
    rejected provider sign-ups in the last `days` days, grouped by account
    so unusual activity stands out."""
    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    recent = [e for e in audit.read_entries() if e.get("ts", "") >= since]
    login = [e for e in recent if e.get("route") == "/api/auth/login"]
    refused = [e for e in recent if e.get("status") in (403, 404)
               and not (e.get("route") or "").startswith("/api/auth/")]
    rejected = [o for o in records.orgs.all()
                if o.status == records.REJECTED and o.reviewed_at >= since]
    return {
        "days": days,
        "failed_sign_ins": _group([e for e in login if e.get("status") == 401]),
        "lockouts": _group([e for e in login if e.get("status") == 429]),
        "refused_requests": _group(refused),
        "rejected_sign_ups": [{"org_id": o.org_id, "name": o.name, "signed_up_by": o.signed_up_by,
                               "reviewed_at": o.reviewed_at, "review_note": o.review_note}
                              for o in rejected],
    }


# ── Sample policies ──────────────────────────────────────────────────

def _sample_health(entry: dict) -> dict:
    from . import policies  # paths are read at call time so tests can redirect them

    chunk_file = policies.CHUNK_DIR / f"{entry['document_id']}.json"
    try:
        chunk_count = len(json.loads(chunk_file.read_text())) if chunk_file.exists() else 0
    except ValueError:
        chunk_count = 0
    version = entry.get("chunker_version", 0)
    missing = [f for f in METADATA_FIELDS if not entry.get(f)]
    problems = []
    if entry.get("status") != "completed":
        problems.append(f"status {entry.get('status')}")
    if chunk_count == 0:
        problems.append("no searchable text")
    if version < CHUNKER_VERSION:
        problems.append("built with an older chunker")
    return {"document_id": entry["document_id"], "filename": entry["filename"],
            "name": entry.get("display_name") or entry.get("plan_name") or entry["filename"],
            "status": entry.get("status"), "page_count": entry.get("page_count"),
            "chunk_count": chunk_count, "chunker_version": version,
            "current_chunker_version": CHUNKER_VERSION,
            "metadata_found": [f for f in METADATA_FIELDS if entry.get(f)],
            "metadata_missing": missing, "problems": problems, "healthy": not problems}


@router.get("/samples")
async def sample_health(_: User = Depends(_oversee)) -> list[dict]:
    """Each sample policy: pages, searchable chunks, chunker version and
    which plan details were found."""
    return [_sample_health(e) for e in registry.load() if is_sample(e)]


@router.post("/samples/{document_id}/reprocess")
async def reprocess_sample(document_id: str = PathParam(pattern=DOCUMENT_ID_PATTERN),
                           _: User = Depends(_oversee)) -> dict:
    """Rebuild a sample's search index and plan details from its PDF."""
    from . import policies

    entries = registry.load()
    for i, e in enumerate(entries):
        if e["document_id"] == document_id and is_sample(e):
            rebuilt = ingest.reprocess(e, [policies.UPLOAD_DIR, registry.POLICY_DIR], policies.CHUNK_DIR)
            if rebuilt is None:
                raise HTTPException(409, "The sample's PDF file can't be found")
            entries[i] = rebuilt
            registry.save(entries)
            return _sample_health(rebuilt)
    raise HTTPException(404, "Document not found")
