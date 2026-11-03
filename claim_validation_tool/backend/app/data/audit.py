"""Append-only audit log of API requests, one JSON event per line.

Every event carries the hash of the one before it, so editing or deleting a line breaks the
chain from that point on (`verify`). The file is created readable only by its owner.

Retention: events are kept for at least RCM_AUDIT_RETENTION_YEARS years (default and
minimum 6, HIPAA's retention period for required documentation, 45 CFR 164.316(b)(2)).
When the first event of a new year is recorded, the year before is closed into its own file
(audit.jsonl -> audit-2026.jsonl) and the chain carries on in a new audit.jsonl. A closed
year can be deleted once its retention period is over (`python -m app.orgs audit-purge`,
never automatic); audit-purged.json then records where the remaining chain starts, so
`verify` still checks every event that's left.
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

from cryptography.fernet import Fernet

from app.data.orgs import org_cipher_for, org_file
from app.data.secure_files import append_line, iter_lines, write_bytes
from app.models import AuditEvent, AuditOutcome, AuditQuery, AuditVerification, Role

DEFAULT_AUDIT_FILE = Path(__file__).resolve().parents[2] / "logs" / "audit.jsonl"
GENESIS_HASH = "0" * 64
RETENTION_ENV = "RCM_AUDIT_RETENTION_YEARS"
MIN_RETENTION_YEARS = 6


def retention_years() -> int:
    """How many years events are kept (RCM_AUDIT_RETENTION_YEARS); never less than 6."""
    raw = os.environ.get(RETENTION_ENV, "").strip()
    try:
        years = int(raw) if raw else MIN_RETENTION_YEARS
    except ValueError:
        raise ValueError(f"{RETENTION_ENV} must be a whole number of years, not {raw!r}") from None
    if years < MIN_RETENTION_YEARS:
        raise ValueError(
            f"{RETENTION_ENV} must be at least {MIN_RETENTION_YEARS} "
            "(HIPAA's retention period, 45 CFR 164.316(b)(2))"
        )
    return years


def closed_year_files(path: Path) -> list[tuple[int, Path]]:
    """(year, file) for each closed year of the log at `path`, oldest first."""
    years = []
    for closed in path.parent.glob(f"{path.stem}-*{path.suffix}"):
        label = closed.name[len(path.stem) + 1 : -len(path.suffix)]
        if label.isdigit():
            years.append((int(label), closed))
    return sorted(years)


def _now() -> datetime:
    return datetime.now(UTC)


def _year(line: str) -> int:
    return int(json.loads(line)["at"][:4])


def _event_hash(fields: dict[str, Any]) -> str:
    """SHA-256 over the event (without its own hash), in a fixed key order."""
    body = {k: v for k, v in fields.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def outcome_for(status_code: int) -> AuditOutcome:
    if status_code in (401, 403):
        return AuditOutcome.DENIED
    return AuditOutcome.SUCCESS if status_code < 400 else AuditOutcome.FAILED


class AuditLog:
    def __init__(self, path: Path | None = None, cipher: Fernet | None = None) -> None:
        self.path = path
        self._cipher = cipher  # each line encrypted on its own; the chain is over plain text
        self._memory: list[str] = []  # events when there's no file (tests)
        self._lock = Lock()
        self._seq, self._last_hash = 0, GENESIS_HASH
        self._active_year: int | None = None  # latest year in the active file
        if (marker := self._purge_marker()) is not None:
            self._seq, self._last_hash = marker["last_seq"], marker["last_hash"]
        last = None
        for last in self._lines():
            pass
        if last is not None:
            event = json.loads(last)
            self._seq, self._last_hash = event["seq"], event["hash"]
        self._active_year = max((_year(line) for line in self._active_lines()), default=None)

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
                "at": _now().isoformat(),
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
            self._close_year(int(fields["at"][:4]))
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
        """Recompute the hash chain; the first event that doesn't match was altered. After a
        purge the chain starts where the deleted years ended."""
        marker = self._purge_marker()
        prev, after = (marker["last_hash"], marker["last_seq"]) if marker else (GENESIS_HASH, 0)
        result = {
            "retention_years": retention_years(),
            "purged_through_year": marker["through_year"] if marker else None,
            "purged_at": marker["purged_at"] if marker else None,
        }
        count = 0
        for line in self._lines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                return AuditVerification(ok=False, events=count + 1, first_bad_seq=after + count + 1, **result)
            if isinstance(event.get("seq"), int) and event["seq"] <= after:
                continue  # in a year already purged (its file not yet deleted)
            count += 1
            if event.get("prev_hash") != prev or _event_hash(event) != event.get("hash"):
                return AuditVerification(
                    ok=False, events=count, first_bad_seq=event.get("seq", after + count), **result
                )
            prev = event["hash"]
        return AuditVerification(ok=True, events=count, **result)

    def lines(self) -> Iterator[str]:
        """Every event as stored (decrypted JSON), oldest first, closed years included."""
        return self._lines()

    def closed_years(self) -> list[tuple[int, Path]]:
        """The closed years' files, oldest first."""
        return closed_year_files(self.path) if self.path is not None else []

    def purge(self, *, now: datetime | None = None, dry_run: bool = False) -> list[tuple[int, int]]:
        """Delete the closed years whose retention period is over: (year, events) for each.
        A year is due once `retention_years()` full years have passed since it ended. Refused
        if the chain doesn't verify, so evidence of tampering is never deleted."""
        keep = retention_years()
        current = (now or _now()).year
        due = [(year, path) for year, path in self.closed_years() if year + keep < current]
        if not due:
            return []
        check = self.verify()
        if not check.ok:
            raise ValueError(
                f"{self.path}: the hash chain is broken at event {check.first_bad_seq}; "
                "investigate before deleting anything"
            )
        removed, last = [], None
        for year, path in due:
            count = 0
            for last in iter_lines(path, self._cipher):
                count += 1
            removed.append((year, count))
        if dry_run:
            return removed
        if last is not None:
            event = json.loads(last)
            # Written first: if deleting a file fails, verify still starts in the right place
            marker = {
                "through_year": due[-1][0],
                "last_seq": event["seq"],
                "last_hash": event["hash"],
                "purged_at": _now().isoformat(),
                "retention_years": keep,
            }
            write_bytes(self._marker_path(), json.dumps(marker, indent=2).encode())
        for _, path in due:
            path.unlink()
        return removed

    def _marker_path(self) -> Path:
        assert self.path is not None
        return self.path.with_name(f"{self.path.stem}-purged.json")

    def _purge_marker(self) -> dict[str, Any] | None:
        if self.path is None or not self._marker_path().exists():
            return None
        return json.loads(self._marker_path().read_text())

    def _close_year(self, year: int) -> None:
        """Before the first event of a later year: move the active file to its year's file.
        If the clock goes back, events stay in the active file, so the files stay in order."""
        if self._active_year is not None and year <= self._active_year:
            return
        if self.path is None or self._active_year is None or not self.path.exists():
            self._active_year = year
            return
        closed = self.path.with_name(f"{self.path.stem}-{self._active_year}{self.path.suffix}")
        if closed.exists():  # the clock went back and forth: keep both, in order
            with closed.open("ab") as f:
                f.write(self.path.read_bytes())
            self.path.unlink()
        else:
            self.path.replace(closed)
        self._active_year = year

    def _active_lines(self) -> Iterator[str]:
        if self.path is None:
            yield from self._memory
        elif self.path.exists():
            yield from iter_lines(self.path, self._cipher)

    def _lines(self) -> Iterator[str]:
        for _, path in self.closed_years():
            yield from iter_lines(path, self._cipher)
        yield from self._active_lines()

    def _append(self, line: str) -> None:
        if self.path is None:
            self._memory.append(line)
            return
        append_line(self.path, line, self._cipher)


@lru_cache(maxsize=None)
def get_audit_log(org_id: str) -> AuditLog:
    """The organisation's audit log, in its folder; only its administrators read it."""
    return AuditLog(org_file(org_id, "logs/audit.jsonl"), org_cipher_for(org_id))


@lru_cache(maxsize=1)
def get_platform_audit_log() -> AuditLog:
    """Requests that belong to no organisation (e.g. sign-in with an unknown username),
    appended to RCM_AUDIT_FILE."""
    return AuditLog(Path(os.environ.get("RCM_AUDIT_FILE", DEFAULT_AUDIT_FILE)))
