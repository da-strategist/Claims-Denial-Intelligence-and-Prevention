"""Append-only audit log of API requests, one JSON event per line.

Every event carries the hash of the one before it, so editing or deleting a line breaks the
chain from that point on (`verify`). The file is created readable only by its owner.
"""

import hashlib
import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any

from app.models import AuditEvent, AuditOutcome, AuditQuery, AuditVerification, Role

DEFAULT_AUDIT_FILE = Path(__file__).resolve().parents[2] / "logs" / "audit.jsonl"
GENESIS_HASH = "0" * 64


def _event_hash(fields: dict[str, Any]) -> str:
    """SHA-256 over the event (without its own hash), in a fixed key order."""
    body = {k: v for k, v in fields.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def outcome_for(status_code: int) -> AuditOutcome:
    if status_code in (401, 403):
        return AuditOutcome.DENIED
    return AuditOutcome.SUCCESS if status_code < 400 else AuditOutcome.FAILED


class AuditLog:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._memory: list[str] = []  # events when there's no file (tests)
        self._lock = Lock()
        self._seq, self._last_hash = 0, GENESIS_HASH
        last = None
        for last in self._lines():
            pass
        if last is not None:
            event = json.loads(last)
            self._seq, self._last_hash = event["seq"], event["hash"]

    def record(
        self,
        *,
        username: str | None,
        role: Role | None,
        action: str,
        status_code: int,
        records: dict[str, str] | None = None,
        query: dict[str, str] | None = None,
        detail: dict[str, Any] | None = None,
        client_ip: str | None = None,
    ) -> AuditEvent:
        with self._lock:
            fields = {
                "seq": self._seq + 1,
                "at": datetime.now(UTC).isoformat(),
                "username": username,
                "role": role,
                "action": action,
                "records": records or {},
                "query": query or {},
                "detail": detail or {},
                "status_code": status_code,
                "outcome": outcome_for(status_code),
                "client_ip": client_ip,
                "prev_hash": self._last_hash,
            }
            fields["hash"] = _event_hash(json.loads(json.dumps(fields, default=str)))
            line = json.dumps(fields, default=str)
            self._append(line)
            self._seq, self._last_hash = fields["seq"], fields["hash"]
        return AuditEvent.model_validate_json(line)

    def events(self) -> list[AuditEvent]:
        """Every event, oldest first."""
        return [AuditEvent.model_validate_json(line) for line in self._lines()]

    def search(self, query: AuditQuery) -> list[AuditEvent]:
        """Matching events, newest first."""
        matches = []
        for line in reversed(list(self._lines())):
            event = AuditEvent.model_validate_json(line)
            if query.username and event.username != query.username.lower():
                continue
            if query.record_id and query.record_id.upper() not in event.records.values():
                continue
            if query.outcome and event.outcome != query.outcome:
                continue
            matches.append(event)
            if len(matches) == query.limit:
                break
        return matches

    def verify(self) -> AuditVerification:
        """Recompute the hash chain; the first event that doesn't match was altered."""
        prev, count = GENESIS_HASH, 0
        for count, line in enumerate(self._lines(), start=1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                return AuditVerification(ok=False, events=count, first_bad_seq=count)
            if event.get("prev_hash") != prev or _event_hash(event) != event.get("hash"):
                return AuditVerification(ok=False, events=count, first_bad_seq=event.get("seq", count))
            prev = event["hash"]
        return AuditVerification(ok=True, events=count)

    def _lines(self) -> Iterator[str]:
        if self.path is None:
            yield from self._memory
        elif self.path.exists():
            with self.path.open() as f:
                yield from (line for line in f if line.strip())

    def _append(self, line: str) -> None:
        if self.path is None:
            self._memory.append(line)
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a") as f:
            f.write(line + "\n")


@lru_cache(maxsize=1)
def get_audit_log() -> AuditLog:
    """Process-wide audit log appended to RCM_AUDIT_FILE."""
    return AuditLog(Path(os.environ.get("RCM_AUDIT_FILE", DEFAULT_AUDIT_FILE)))
