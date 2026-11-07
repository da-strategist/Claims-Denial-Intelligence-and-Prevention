"""Append-only audit log of API requests, one JSON event per line.

Every event carries the hash of the one before it, so editing or deleting a line breaks the
chain from that point on (`verify`). The file is created readable only by its owner.

The chain alone can't show that the newest events were removed, so audit-head.json keeps the
number and hash of the latest event, encrypted with the organisation's key where the log is.
If the log no longer reaches that event, `verify` fails, and the file stays as it is so the
evidence isn't overwritten. This catches removal by anyone without the key. It can't catch an
older copy of the log and this file being restored together: that needs a copy kept elsewhere.

Retention: events are kept for at least RCM_AUDIT_RETENTION_YEARS years (default and
minimum 6, HIPAA's retention period for required documentation, 45 CFR 164.316(b)(2)).
When the first event of a new year is recorded, the year before is closed into its own file
(audit.jsonl -> audit-2026.jsonl) and the chain carries on in a new audit.jsonl. A closed
year can be deleted once its retention period is over (`python -m app.orgs audit-purge`,
never automatic). The purge is itself an event in the chain, saying who ran it and what went;
audit-purged.json then records where the remaining chain starts, so `verify` still checks every
event that's left, and fails if that file exists with no matching event.

More than one process can write a log (the API, and audit-purge beside it), so writes take a
file lock and pick up the other's latest event first.
"""

import fcntl
import getpass
import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any

from cryptography.fernet import Fernet

from app.data.orgs import org_cipher_for, org_file
from app.data.secure_files import (
    EncryptionError,
    append_line,
    is_encrypted,
    iter_lines,
    read_text,
    write_bytes,
    write_text,
)
from app.models import AuditEvent, AuditOutcome, AuditQuery, AuditVerification, Role

DEFAULT_AUDIT_FILE = Path(__file__).resolve().parents[2] / "logs" / "audit.jsonl"
GENESIS_HASH = "0" * 64
RETENTION_ENV = "RCM_AUDIT_RETENTION_YEARS"
MIN_RETENTION_YEARS = 6
PURGE_ACTION = "CLI audit-purge"


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


def _parsed(line: str) -> dict[str, Any] | None:
    """A line as an event, or None if it isn't one (verify reports that as tampering; it
    mustn't stop the log loading)."""
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(event, dict) or not {"seq", "hash", "at"} <= event.keys():
        return None
    return event


def _year(event: dict[str, Any]) -> int | None:
    label = str(event["at"])[:4]
    return int(label) if label.isdigit() else None


def _event_hash(fields: dict[str, Any]) -> str:
    """SHA-256 over the event (without its own hash), in a fixed key order."""
    body = {k: v for k, v in fields.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def outcome_for(status_code: int) -> AuditOutcome:
    if status_code in (401, 403):
        return AuditOutcome.DENIED
    return AuditOutcome.SUCCESS if status_code < 400 else AuditOutcome.FAILED


class _HeadScan:
    """What a pass over the log finds out about the recorded head and past purges."""

    def __init__(self, read: dict[str, Any] | None) -> None:
        self.head = read
        self.unreadable = False
        self.found_hash: str | None = None
        self.started = False
        self.purges_logged: set[int] = set()

    def see(self, event: dict[str, Any]) -> None:
        if self.head is not None and event.get("seq") == self.head["seq"]:
            self.found_hash = event.get("hash")
        if event.get("head_started"):
            self.started = True
        if event.get("action") == PURGE_ACTION:
            self.purges_logged.add((event.get("detail") or {}).get("through_year"))


class AuditLog:
    def __init__(self, path: Path | None = None, cipher: Fernet | None = None) -> None:
        self.path = path
        self._cipher = cipher  # each line encrypted on its own; the chain is over plain text
        self._memory: list[str] = []  # events when there's no file (tests)
        self._lock = Lock()
        self._load_state()

    def _load_state(self) -> None:
        """Where the chain has got to, from the files."""
        marker = self._purge_marker()
        self._seq, self._last_hash = (marker["last_seq"], marker["last_hash"]) if marker else (0, GENESIS_HASH)
        scan = self._new_scan()
        for line in self._lines():
            if (event := _parsed(line)) is not None:
                scan.see(event)
                self._seq, self._last_hash = event["seq"], event["hash"]
        active = (_parsed(line) for line in self._active_lines())
        self._active_year = max((y for e in active if e and (y := _year(e)) is not None), default=None)
        # Once the log doesn't reach the recorded head, the head is evidence: it stops moving
        self._head_broken = self._head_problem(scan, marker)
        self._stamp = self._file_stamp()

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
        with self._lock, self._interprocess_lock():
            if self._file_stamp() != self._stamp:  # another process wrote to the log
                self._load_state()
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
            if self.path is not None and not self._head_broken and not self._head_path().exists():
                # In the chain, so deleting the head file later can't pass as never having had one
                fields["head_started"] = True
            fields["hash"] = _event_hash(json.loads(json.dumps(fields, default=str)))
            line = json.dumps(fields, default=str)
            self._close_year(int(fields["at"][:4]))
            self._append(line)
            self._seq, self._last_hash = fields["seq"], fields["hash"]
            if self.path is not None and not self._head_broken:
                head = json.dumps({"seq": fields["seq"], "hash": fields["hash"]})
                write_text(self._head_path(), head, self._cipher)
            self._stamp = self._file_stamp()
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
            "purged_by": marker.get("purged_by") if marker else None,
        }
        count = 0
        scan = self._new_scan()
        for line in self._lines():
            if (event := _parsed(line)) is None:
                return AuditVerification(ok=False, events=count + 1, first_bad_seq=after + count + 1, **result)
            scan.see(event)
            if isinstance(event.get("seq"), int) and event["seq"] <= after:
                continue  # in a year already purged (its file not yet deleted)
            count += 1
            if event.get("prev_hash") != prev or _event_hash(event) != event.get("hash"):
                return AuditVerification(
                    ok=False, events=count, first_bad_seq=event.get("seq", after + count), **result
                )
            prev = event["hash"]
        if marker and marker["through_year"] not in scan.purges_logged:
            return AuditVerification(ok=False, events=count, first_bad_seq=after + 1, **result)
        if self._head_problem(scan, marker):
            return AuditVerification(ok=False, events=count, first_bad_seq=after + count + 1, **result)
        return AuditVerification(ok=True, events=count, **result)

    def lines(self) -> Iterator[str]:
        """Every event as stored (decrypted JSON), oldest first, closed years included."""
        return self._lines()

    def closed_years(self) -> list[tuple[int, Path]]:
        """The closed years' files, oldest first."""
        return closed_year_files(self.path) if self.path is not None else []

    def purge(
        self, *, by: str | None = None, now: datetime | None = None, dry_run: bool = False
    ) -> list[tuple[int, int]]:
        """Delete the closed years whose retention period is over: (year, events) for each.
        A year is due once `retention_years()` full years have passed since it ended. Refused
        if the chain doesn't verify, so evidence of tampering is never deleted. A real purge
        says who is running it (`by`), and is recorded in the log before anything is deleted."""
        if not dry_run and not by:
            raise ValueError("Say who is running the purge")
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
        self.record(
            username=by,
            role=None,
            action=PURGE_ACTION,
            status_code=200,
            detail={
                "through_year": due[-1][0],
                "years": [{"year": year, "events": count} for year, count in removed],
                "retention_years": keep,
                "os_user": getpass.getuser(),
            },
        )
        if last is not None:
            event = json.loads(last)
            # Written first: if deleting a file fails, verify still starts in the right place
            marker = {
                "through_year": due[-1][0],
                "last_seq": event["seq"],
                "last_hash": event["hash"],
                "purged_at": _now().isoformat(),
                "purged_by": by,
                "retention_years": keep,
            }
            write_bytes(self._marker_path(), json.dumps(marker, indent=2).encode())
        for _, path in due:
            path.unlink()
        return removed

    def _new_scan(self) -> _HeadScan:
        try:
            return _HeadScan(self._read_head())
        except ValueError:
            scan = _HeadScan(None)
            scan.unreadable = True
            return scan

    def _head_path(self) -> Path:
        assert self.path is not None
        return self.path.with_name(f"{self.path.stem}-head.json")

    def _read_head(self) -> dict[str, Any] | None:
        """The recorded latest event; None if there's no such file. Raises ValueError if it
        can't be trusted: unreadable, or left plain where the log is encrypted."""
        if self.path is None or not self._head_path().exists():
            return None
        try:
            if self._cipher is not None and not is_encrypted(self._head_path().read_bytes()):
                raise ValueError("not encrypted")
            head = json.loads(read_text(self._head_path(), self._cipher))
            return {"seq": int(head["seq"]), "hash": str(head["hash"])}
        except (EncryptionError, KeyError, TypeError, ValueError) as err:
            raise ValueError(f"{self._head_path().name} can't be read") from err

    def _head_problem(self, scan: "_HeadScan", marker: dict[str, Any] | None) -> bool:
        """Whether the log falls short of the head on record."""
        if self.path is None:
            return False
        if scan.unreadable:
            return True
        if scan.head is None:
            return scan.started  # had a head once, and it's gone; otherwise never had one
        if scan.found_hash is not None:
            return scan.found_hash != scan.head["hash"]
        return not (marker and scan.head["seq"] <= marker["last_seq"])

    def _file_stamp(self) -> tuple[int, int] | None:
        if self.path is None or not self.path.exists():
            return None
        stat = self.path.stat()
        return stat.st_ino, stat.st_size

    @contextmanager
    def _interprocess_lock(self) -> Iterator[None]:
        if self.path is None:
            yield
            return
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(self.path.with_name(f"{self.path.stem}.lock"), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)  # releases the lock

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
