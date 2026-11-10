"""Pilot requests from the public website's form, waiting for a platform account to approve
or decline them on the Platform page.

They hold personal data (name, work email, job title), never patient data, so they're kept
apart from every organisation: in `pilot_requests.json` beside organisations.json, encrypted
with the platform's own data key (in the `_platform` folder, which no organisation ID can
take). A request is deleted RETENTION_DAYS after its decision. Every view, approval and decline
is in the platform audit log (the routes are under /api/platform/).

The public form is open to anyone, so it's limited: a few requests per email address and per
network address a day, a ceiling on requests per hour overall, and on how many can wait.
"""

import json
import secrets
from collections import deque
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from threading import Lock

from cryptography.fernet import Fernet
from pydantic import BaseModel

from app.data.orgs import get_org_registry
from app.data.secure_files import org_cipher, read_text, write_text

PLATFORM_FOLDER = "_platform"  # org IDs start with a letter, so none can be this
REQUESTS_FILE = "pilot_requests.json"
RETENTION_DAYS = 365
PER_EMAIL_PER_DAY = 3
PER_ADDRESS_PER_DAY = 5
PER_HOUR = 30
MAX_PENDING = 200


class PilotStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"


class PilotRequest(BaseModel):
    id: str
    name: str
    email: str
    organization: str
    title: str
    org_type: str
    message: str = ""
    received_at: datetime
    status: PilotStatus = PilotStatus.PENDING
    decided_at: datetime | None = None
    decided_by: str | None = None
    decline_reason: str | None = None
    organisation_id: str | None = None  # the organisation an approval created


class TooManyRequests(RuntimeError):
    """The public form's limits were reached; try again later."""


class RequestNotPending(RuntimeError):
    pass


class PilotRequestStore:
    def __init__(self, path: Path | None = None, cipher: Fernet | None = None) -> None:
        self.path = path
        self._cipher = cipher
        self._lock = Lock()
        self._requests: dict[str, PilotRequest] = {}
        # Recent submissions, in memory only: (when, email, address)
        self._recent: deque[tuple[datetime, str, str]] = deque()
        if path is not None and path.exists():
            saved = json.loads(read_text(path, cipher))
            self._requests = {r["id"]: PilotRequest.model_validate(r) for r in saved["requests"]}

    # --- The public form -----------------------------------------------------------

    def submit(self, *, address: str, **details) -> PilotRequest:
        now = datetime.now(UTC)
        email = details["email"].strip().lower()
        with self._lock:
            self._check_limits(now, email, address)
            request = PilotRequest(
                id=f"PR-{secrets.token_hex(4)}",
                received_at=now,
                **{**details, "email": email},
            )
            self._recent.append((now, email, address))
            self._requests[request.id] = request
            self._save(now)
            return request

    def _check_limits(self, now: datetime, email: str, address: str) -> None:
        while self._recent and now - self._recent[0][0] > timedelta(days=1):
            self._recent.popleft()
        last_hour = [r for r in self._recent if now - r[0] <= timedelta(hours=1)]
        pending = sum(1 for r in self._requests.values() if r.status == PilotStatus.PENDING)
        if (
            sum(1 for r in self._recent if r[1] == email) >= PER_EMAIL_PER_DAY
            or sum(1 for r in self._recent if r[2] == address) >= PER_ADDRESS_PER_DAY
            or len(last_hour) >= PER_HOUR
            or pending >= MAX_PENDING
        ):
            raise TooManyRequests("Too many requests just now. Please try again later, or email us.")

    # --- The Platform page ---------------------------------------------------------

    def all(self) -> list[PilotRequest]:
        """Pending first, then decided; newest first within each."""
        with self._lock:
            self._purge(datetime.now(UTC))
            ordered = sorted(self._requests.values(), key=lambda r: r.received_at, reverse=True)
            return sorted(ordered, key=lambda r: r.status != PilotStatus.PENDING)

    def get(self, request_id: str) -> PilotRequest | None:
        return self._requests.get(request_id)

    def approve(self, request_id: str, by: str, organisation_id: str) -> PilotRequest:
        return self._decide(request_id, by, status=PilotStatus.APPROVED, organisation_id=organisation_id)

    def decline(self, request_id: str, by: str, reason: str) -> PilotRequest:
        return self._decide(request_id, by, status=PilotStatus.DECLINED, decline_reason=reason)

    def _decide(self, request_id: str, by: str, **changes) -> PilotRequest:
        now = datetime.now(UTC)
        with self._lock:
            request = self._requests.get(request_id)
            if request is None:
                raise LookupError(request_id)
            if request.status != PilotStatus.PENDING:
                raise RequestNotPending(f"{request_id} was already {request.status}")
            request = request.model_copy(update={**changes, "decided_at": now, "decided_by": by})
            self._requests[request_id] = request
            self._save(now)
            return request

    # --- Storage -------------------------------------------------------------------

    def _purge(self, now: datetime) -> None:
        """Caller holds the lock. Decided requests go RETENTION_DAYS after the decision."""
        cutoff = now - timedelta(days=RETENTION_DAYS)
        expired = [r.id for r in self._requests.values() if r.decided_at and r.decided_at < cutoff]
        for request_id in expired:
            del self._requests[request_id]
        if expired:
            self._write()

    def _save(self, now: datetime) -> None:
        self._purge(now)
        self._write()

    def _write(self) -> None:
        if self.path is None:
            return
        payload = {"requests": [r.model_dump(mode="json") for r in self._requests.values()]}
        write_text(self.path, json.dumps(payload, indent=2), self._cipher)


@lru_cache(maxsize=1)
def get_pilot_requests() -> PilotRequestStore:
    folder = get_org_registry().root / PLATFORM_FOLDER
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    return PilotRequestStore(folder / REQUESTS_FILE, org_cipher(folder))
