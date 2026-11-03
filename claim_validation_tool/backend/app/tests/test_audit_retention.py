"""Audit log retention: one file per closed year, kept at least 6 years, then deletable
without breaking the hash chain for what's left."""

import io
import json
import zipfile
from datetime import UTC, datetime

import pytest

from app.data import audit
from app.data.audit import AuditLog, get_audit_log, retention_years
from app.data.org_lifecycle import encrypt_organisation, export_organisation
from app.data.orgs import org_cipher_for
from app.models import Role
from app.orgs import main as orgs_cli
from app.tests.conftest import org_folder


@pytest.fixture
def clock(monkeypatch):
    """Set the audit log's clock: clock(2019) puts the next events in 2019."""
    now = {"at": datetime(2019, 6, 1, tzinfo=UTC)}
    monkeypatch.setattr(audit, "_now", lambda: now["at"])

    def set_year(year: int, month: int = 6) -> None:
        now["at"] = datetime(year, month, 1, tzinfo=UTC)

    return set_year


def record(log: AuditLog, n: int = 1) -> None:
    for _ in range(n):
        log.record(username="a", role=Role.ADMIN, action="GET /x", status_code=200)


def yearly_log(tmp_path, clock, years=range(2018, 2027)) -> AuditLog:
    log = AuditLog(tmp_path / "audit.jsonl")
    for year in years:
        clock(year)
        record(log, 2)
    return log


def test_each_year_is_closed_into_its_own_file(tmp_path, clock):
    log = yearly_log(tmp_path, clock, years=[2024, 2025, 2026])
    assert [year for year, _ in log.closed_years()] == [2024, 2025]
    assert (tmp_path / "audit-2024.jsonl").stat().st_mode & 0o777 == 0o600
    assert len((tmp_path / "audit.jsonl").read_text().splitlines()) == 2  # 2026 so far
    check = log.verify()
    assert (check.ok, check.events) == (True, 6)  # one chain across the files
    # Reopened after a year closed, the chain carries on from the closed year's last event
    clock(2027)
    AuditLog(tmp_path / "audit.jsonl").record(username="b", role=None, action="GET /", status_code=200)
    reopened = AuditLog(tmp_path / "audit.jsonl")
    clock(2027, 7)
    record(reopened)
    assert reopened.verify().ok
    assert [e.seq for e in reopened.events()] == list(range(1, 9))


def test_a_clock_going_back_keeps_events_in_order(tmp_path, clock):
    log = AuditLog(tmp_path / "audit.jsonl")
    clock(2026)
    record(log)
    clock(2025)  # e.g. corrected around New Year
    record(log)
    clock(2026, 7)
    record(log)
    assert log.closed_years() == []
    clock(2027)
    record(log)
    assert [year for year, _ in log.closed_years()] == [2026]
    assert log.verify().ok and log.verify().events == 4


def test_tampering_in_a_closed_year_is_still_detected(tmp_path, clock):
    yearly_log(tmp_path, clock, years=[2025, 2026])
    path = tmp_path / "audit-2025.jsonl"
    lines = path.read_text().splitlines()
    edited = json.loads(lines[1])
    edited["username"] = "someone-else"
    path.write_text("\n".join([lines[0], json.dumps(edited)]) + "\n")
    assert AuditLog(tmp_path / "audit.jsonl").verify().first_bad_seq == 2


def test_only_years_past_retention_are_purged(tmp_path, clock):
    log = yearly_log(tmp_path, clock)  # 2018-2026, two events a year
    clock(2026)
    # 6 years: 2019 ended 31 Dec 2019 and is kept through 2025; 2020 is kept through 2026
    assert log.purge(dry_run=True) == [(2018, 2), (2019, 2)]
    assert (tmp_path / "audit-2018.jsonl").exists()  # a dry run deletes nothing

    assert log.purge() == [(2018, 2), (2019, 2)]
    assert [year for year, _ in log.closed_years()] == list(range(2020, 2026))
    check = AuditLog(tmp_path / "audit.jsonl").verify()
    assert (check.ok, check.events, check.purged_through_year, check.retention_years) == (True, 14, 2019, 6)
    assert check.purged_at is not None
    assert log.purge() == []  # nothing more is due this year

    # New events still chain on, and the next year's purge moves the starting point on
    record(log)
    clock(2027)
    assert log.purge() == [(2020, 2)]
    reopened = AuditLog(tmp_path / "audit.jsonl")
    assert reopened.verify().ok and reopened.verify().purged_through_year == 2020
    record(reopened)
    assert reopened.verify().ok


def test_a_longer_retention_period_keeps_more(tmp_path, clock, monkeypatch):
    log = yearly_log(tmp_path, clock)
    monkeypatch.setenv("RCM_AUDIT_RETENTION_YEARS", "7")
    clock(2026)
    assert log.purge() == [(2018, 2)]


@pytest.mark.parametrize("value", ["5", "0", "six"])
def test_retention_under_six_years_is_refused(monkeypatch, value):
    monkeypatch.setenv("RCM_AUDIT_RETENTION_YEARS", value)
    with pytest.raises(ValueError, match="RCM_AUDIT_RETENTION_YEARS"):
        retention_years()


def test_a_broken_chain_is_never_purged(tmp_path, clock):
    log = yearly_log(tmp_path, clock)
    path = tmp_path / "audit-2018.jsonl"
    path.write_text(path.read_text().splitlines()[0] + "\n")  # an event removed
    clock(2026)
    with pytest.raises(ValueError, match="hash chain is broken"):
        log.purge()
    assert path.exists()


def test_a_purge_interrupted_before_deleting_still_verifies(tmp_path, clock, monkeypatch):
    log = yearly_log(tmp_path, clock)
    clock(2026)
    monkeypatch.setattr("pathlib.Path.unlink", lambda self, missing_ok=False: None)
    log.purge()
    assert (tmp_path / "audit-2018.jsonl").exists()  # left behind, but already purged
    check = AuditLog(tmp_path / "audit.jsonl").verify()
    assert (check.ok, check.events) == (True, 14)


def test_purge_command_covers_every_organisation(client, clock, capsys):
    client.get("/api/claims")  # meridian's log, written by the API in 2019
    clock(2026)
    record(get_audit_log("meridian"))
    assert orgs_cli(["audit-purge", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "meridian: would delete" in out and "events)" in out
    assert "platform: nothing older than 6 years" in out
    assert orgs_cli(["audit-purge"]) == 0
    assert "meridian: deleted" in capsys.readouterr().out
    assert get_audit_log("meridian").verify().ok


def test_export_and_encryption_cover_closed_years(anon_client, clock):
    folder = org_folder("lakeside")
    log = AuditLog(folder / "logs/audit.jsonl")  # written before encryption was on
    clock(2025)
    record(log)
    clock(2026)
    record(log)
    done = encrypt_organisation("lakeside")
    assert "encrypted lakeside/logs/audit-2025.jsonl" in done
    assert "encrypted lakeside/logs/audit.jsonl" in done
    encrypted = AuditLog(folder / "logs/audit.jsonl", org_cipher_for("lakeside"))
    assert encrypted.verify().ok and encrypted.verify().events == 2

    zipped, manifest = export_organisation("lakeside", "admin")
    exported = next(f for f in manifest["files"] if f["path"] == "app/audit.jsonl")
    assert exported["bytes"] > 0
    lines = zipfile.ZipFile(io.BytesIO(zipped)).read("app/audit.jsonl").decode().splitlines()
    assert [json.loads(line)["seq"] for line in lines] == [1, 2]


def test_verify_endpoint_reports_the_retention_policy(client):
    body = client.get("/api/audit/verify").json()
    assert (body["ok"], body["retention_years"], body["purged_through_year"]) == (True, 6, None)
