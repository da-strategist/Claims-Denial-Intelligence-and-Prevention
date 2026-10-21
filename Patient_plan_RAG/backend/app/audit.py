"""Append-only, hash-chained audit log of API access.

One JSON line per API request (health checks excepted): time, user, role,
route, document touched, status, client address. Never request bodies,
questions, or answers. Each line carries the SHA-256 of the previous line, so
editing or deleting a line breaks the chain:

    python -m backend.app.audit verify

Routers name the document they touched with `audit_document(request, id)`
when it isn't a path parameter (e.g. chat's policy_id in the request body).
"""

import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from fastapi import Request

BASE_DIR = Path(__file__).resolve().parents[2]
AUDIT_FILE = Path(os.getenv("AUDIT_FILE", str(BASE_DIR / "data" / "audit.log")))
GENESIS = "0" * 64

_lock = Lock()


def _hash(line: str) -> str:
    return hashlib.sha256(line.encode()).hexdigest()


def _last_hash(path: Path) -> str:
    if not path.exists() or path.stat().st_size == 0:
        return GENESIS
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        pos = f.tell() - 1
        while pos > 0:  # find the start of the last line
            f.seek(pos - 1)
            if f.read(1) == b"\n":
                break
            pos -= 1
        f.seek(max(pos, 0))
        return _hash(f.readline().decode().rstrip("\n"))


def record(entry: dict, path: Path | None = None) -> None:
    """Append one entry, chained to the previous line."""
    path = path or AUDIT_FILE
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"ts": datetime.now(UTC).isoformat(), **entry,
                           "prev": _last_hash(path)}, sort_keys=True)
        new = not path.exists()
        with path.open("a") as f:
            f.write(line + "\n")
        if new:
            os.chmod(path, 0o600)


def verify(path: Path | None = None) -> tuple[bool, int, str]:
    """(ok, lines checked, problem)."""
    path = path or AUDIT_FILE
    if not path.exists():
        return True, 0, ""
    prev, n = GENESIS, 0
    for n, line in enumerate(path.read_text().splitlines(), start=1):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            return False, n, f"line {n} is not valid JSON"
        if entry.get("prev") != prev:
            return False, n, f"chain broken at line {n} (edited, inserted or deleted lines)"
        prev = _hash(line)
    return True, n, ""


def read_entries(path: Path | None = None) -> list[dict]:
    """All entries, oldest first (malformed lines skipped)."""
    path = path or AUDIT_FILE
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# ── Plain-words descriptions ─────────────────────────────────────────

# (method, route pattern, label). Checked in order; first match wins.
_ACTIONS = [
    ("POST", r"/api/auth/register/provider", "Provider signed up"),
    ("POST", r"/api/auth/register", "Signed up"),
    ("POST", r"/api/auth/logout", "Signed out"),
    ("POST", r"/api/auth/password", "Changed password"),
    ("GET", r"/api/hospital/patients/\{patient_id\}", "Opened patient record"),
    ("POST", r"/api/hospital/patients", "Added a patient"),
    ("PATCH", r"/api/hospital/patients/\{patient_id\}", "Changed patient record"),
    ("DELETE", r"/api/hospital/patients/\{patient_id\}", "Deleted patient record"),
    ("POST", r"/api/hospital/patients/\{patient_id\}/merge", "Merged patient records"),
    ("POST", r".*/checklists", "Saved a prior-auth checklist"),
    ("PATCH", r".*/checklists/.*", "Updated a prior-auth checklist"),
    ("DELETE", r".*/checklists/.*", "Deleted a prior-auth checklist"),
    ("PATCH", r"/api/hospital/shared/.*", "Filed a shared policy"),
    ("PATCH", r"/api/hospital/connections/.*", "Attached a person to a patient record"),
    ("POST", r"/api/hospital/staff", "Added staff"),
    ("PATCH", r"/api/hospital/staff/.*", "Changed a staff account"),
    ("POST", r"/api/hospital/staff/.*/reset-password", "Reset a staff password"),
    ("PATCH", r"/api/hospital/profile", "Updated the organisation profile"),
    ("GET", r"/api/policies/\{document_id\}", "Viewed a policy"),
    ("GET", r"/api/policies/\{document_id\}/summary", "Viewed a policy summary"),
    ("GET", r"/api/policies/\{document_id\}/chunks", "Read a policy's text"),
    ("POST", r"/api/policies/upload", "Uploaded a policy"),
    ("PATCH", r"/api/policies/\{document_id\}", "Renamed a policy"),
    ("DELETE", r"/api/policies/\{document_id\}", "Deleted a policy"),
    ("POST", r"/api/chat", "Asked a question"),
    ("POST", r"/api/coverage/assess", "Ran a coverage check"),
    ("POST", r"/api/coverage/auth-checklist", "Generated a prior-auth checklist"),
    ("POST", r"/api/shares", "Shared a policy"),
    ("DELETE", r"/api/shares/.*", "Stopped sharing a policy"),
    ("DELETE", r"/api/me/sharing/.*", "Removed a provider's access"),
    ("POST", r"/api/me/providers", "Added a provider"),
    ("PATCH", r"/api/me/providers/.*", "Changed a provider"),
    ("DELETE", r"/api/me/providers/.*", "Removed a provider"),
    ("PATCH", r"/api/me/profile", "Updated their profile"),
    ("GET", r"/api/me/export", "Downloaded their data"),
    ("POST", r"/api/me/sign-out-everywhere", "Signed out everywhere"),
    ("DELETE", r"/api/me", "Deleted their account"),
    ("POST", r"/api/admin/orgs", "Added a provider"),
    ("POST", r"/api/admin/orgs/.*/approve", "Approved a provider"),
    ("POST", r"/api/admin/orgs/.*/reject", "Rejected a provider"),
    ("PATCH", r"/api/admin/orgs/.*", "Changed a provider's access"),
    ("DELETE", r"/api/admin/orgs/.*", "Deleted a rejected provider"),
    ("PATCH", r"/api/admin/users/.*", "Changed an account's access"),
    ("POST", r"/api/admin/users/.*/reset-password", "Reset a password"),
    ("DELETE", r"/api/admin/users/.*", "Deleted an account"),
    ("POST", r"/api/admin/samples/.*/reprocess", "Re-processed a sample"),
    ("GET", r"/api/admin/audit/verify", "Checked audit integrity"),
]
_ACTION_RES = [(m, re.compile(f"^{r}$"), label) for m, r, label in _ACTIONS]


def describe(entry: dict) -> tuple[str, bool]:
    """(plain-words label, routine). Routine entries are the successful reads
    a page makes when it loads (lists, overviews, the signed-in user);
    everything a person deliberately did, and anything refused, is not."""
    method, route, status = entry.get("method"), entry.get("route") or "", entry.get("status")
    if (method, route) == ("POST", "/api/auth/login"):
        return {401: "Failed sign-in", 429: "Sign-in locked out"}.get(status, "Signed in"), False
    for m, pattern, label in _ACTION_RES:
        if m == method and pattern.match(route):
            return label, False
    if method == "GET":  # a refused load is worth seeing, a successful one is routine
        return f"Loaded {route.removeprefix('/api/')}", (status or 0) < 400
    return f"{method} {route}", False


def audit_document(request: Request, document_id: str | None) -> None:
    """Name the document a request touched (when it isn't in the path)."""
    if document_id:
        request.state.audit_document_id = document_id


def audit_patient(request: Request, patient_id: str | None) -> None:
    """Name the patient record a request concerned (hospital staff)."""
    if patient_id:
        request.state.audit_patient_id = patient_id


def audit_target(request: Request, username: str) -> None:
    """Name the account an admin action touched (when it isn't in the path)."""
    request.state.audit_target = username


def entry_for(request: Request, status: int) -> dict:
    """What gets recorded for a request: identity and target, never content."""
    user = getattr(request.state, "user", None)
    route = request.scope.get("route")
    return {
        "user": user.username if user else getattr(request.state, "audit_username", None),
        "role": user.role.value if user else None,
        "method": request.method,
        "route": route.path if route else request.url.path,
        "document_id": request.path_params.get("document_id")
                       or getattr(request.state, "audit_document_id", None),
        "patient_id": request.path_params.get("patient_id")
                      or getattr(request.state, "audit_patient_id", None),
        "target": request.path_params.get("username")
                  or getattr(request.state, "audit_target", None),
        "status": status,
        "client": request.client.host if request.client else None,
    }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if args != ["verify"]:
        print("usage: python -m backend.app.audit verify", file=sys.stderr)
        return 2
    ok, lines, problem = verify()
    print(f"{'OK' if ok else 'TAMPERED'}: {lines} line(s) checked{'' if ok else ' — ' + problem}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
