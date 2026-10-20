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
