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

    assert log.purge(by="ana") == [(2018, 2), (2019, 2)]
    assert [year for year, _ in log.closed_years()] == list(range(2020, 2026))
    check = AuditLog(tmp_path / "audit.jsonl").verify()
    # The 14 events left, and the purge itself
    assert (check.ok, check.events, check.purged_through_year, check.retention_years) == (True, 15, 2019, 6)
    assert check.purged_by == "ana"
    assert check.purged_at is not None
    assert log.purge(by="ana") == []  # nothing more is due this year

    # New events still chain on, and the next year's purge moves the starting point on
    record(log)
    clock(2027)
    assert log.purge(by="ana") == [(2020, 2)]
    reopened = AuditLog(tmp_path / "audit.jsonl")
    assert reopened.verify().ok and reopened.verify().purged_through_year == 2020
    record(reopened)
    assert reopened.verify().ok


def test_a_longer_retention_period_keeps_more(tmp_path, clock, monkeypatch):
    log = yearly_log(tmp_path, clock)
    monkeypatch.setenv("RCM_AUDIT_RETENTION_YEARS", "7")
    clock(2026)
    assert log.purge(by="ana") == [(2018, 2)]


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
        log.purge(by="ana")
    assert path.exists()


def test_a_purge_interrupted_before_deleting_still_verifies(tmp_path, clock, monkeypatch):
    log = yearly_log(tmp_path, clock)
    clock(2026)
    monkeypatch.setattr("pathlib.Path.unlink", lambda self, missing_ok=False: None)
    log.purge(by="ana")
    assert (tmp_path / "audit-2018.jsonl").exists()  # left behind, but already purged
    check = AuditLog(tmp_path / "audit.jsonl").verify()
    assert (check.ok, check.events) == (True, 15)


def test_purge_command_covers_every_organisation(client, clock, capsys):
    client.get("/api/claims")  # meridian's log, written by the API in 2019
    clock(2026)
    record(get_audit_log("meridian"))
    assert orgs_cli(["audit-purge", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "meridian: would delete" in out and "events)" in out
    assert "platform: nothing older than 6 years" in out
    assert orgs_cli(["audit-purge", "--by", "Ana Diaz"]) == 0
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


def test_a_purge_says_who_ran_it_and_what_went(tmp_path, clock):
    log = yearly_log(tmp_path, clock)
    clock(2026)
    with pytest.raises(ValueError, match="who is running"):
        log.purge()
    assert (tmp_path / "audit-2018.jsonl").exists()
    log.purge(by="Ana Diaz")
    event = log.events()[-1]
    assert (event.username, event.action, event.status_code) == ("Ana Diaz", audit.PURGE_ACTION, 200)
    assert event.detail["through_year"] == 2019
    assert event.detail["years"] == [{"year": 2018, "events": 2}, {"year": 2019, "events": 2}]
    assert event.detail["os_user"]
    assert log.verify().ok


def test_a_dry_run_is_not_recorded(tmp_path, clock):
    log = yearly_log(tmp_path, clock)
    clock(2026)
    before = len(log.events())
    log.purge(dry_run=True)
    assert len(log.events()) == before


def test_the_purge_command_needs_a_name_to_delete(client, clock, capsys):
    client.get("/api/claims")
    clock(2026)
    record(get_audit_log("meridian"))
    assert orgs_cli(["audit-purge"]) == 1
    assert "--by" in capsys.readouterr().err
    assert orgs_cli(["audit-purge", "--dry-run"]) == 0  # looking needs no name
    assert get_audit_log("meridian").closed_years()


def test_a_purge_from_another_process_keeps_the_running_log_intact(tmp_path, clock):
    """The API keeps writing while audit-purge runs beside it, each with its own AuditLog."""
    api = yearly_log(tmp_path, clock)
    clock(2026)
    AuditLog(tmp_path / "audit.jsonl").purge(by="ana")
    record(api, 2)  # the API's next events follow the purge event, not its own last one
    check = AuditLog(tmp_path / "audit.jsonl").verify()
    assert check.ok, check
    assert [e.seq for e in api.events()][-3:] == [19, 20, 21]


def test_a_forged_purge_record_is_caught(tmp_path, clock):
    """Deleting old years and writing the marker by hand leaves no event in the chain."""
    log = yearly_log(tmp_path, clock, years=[2018, 2019, 2026])
    last = json.loads((tmp_path / "audit-2018.jsonl").read_text().splitlines()[-1])
    (tmp_path / "audit-purged.json").write_text(json.dumps({
        "through_year": 2018, "last_seq": last["seq"], "last_hash": last["hash"],
        "purged_at": "2026-01-01T00:00:00+00:00", "retention_years": 6,
    }))
    (tmp_path / "audit-2018.jsonl").unlink()
    check = AuditLog(tmp_path / "audit.jsonl").verify()
    assert (check.ok, check.first_bad_seq) == (False, 3)
    assert log.verify().ok is False


def _truncate(path, keep):
    path.write_text("".join(line + "\n" for line in path.read_text().splitlines()[:keep]))


def test_removing_the_newest_events_is_caught(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    for _ in range(5):
        record(log)
    assert log.verify().ok
    _truncate(path, 3)
    check = AuditLog(path).verify()
    assert (check.ok, check.events, check.first_bad_seq) == (False, 3, 4)


def test_removed_events_stay_caught_after_a_restart_and_new_events(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    for _ in range(5):
        record(log)
    _truncate(path, 3)
    reopened = AuditLog(path)
    for _ in range(4):  # past where the log used to end
        record(reopened)
    check = AuditLog(path).verify()
    assert check.ok is False and check.first_bad_seq == 8
    assert json.loads((tmp_path / "audit-head.json").read_text())["seq"] == 5  # the evidence stays


def test_removed_events_are_caught_while_the_log_is_running(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    for _ in range(5):
        record(log)
    _truncate(path, 3)
    record(log)
    assert log.verify().ok is False


def test_emptying_the_log_is_caught(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    record(log, 3)
    path.unlink()
    check = AuditLog(path).verify()
    assert (check.ok, check.first_bad_seq) == (False, 1)


def test_removing_the_newest_closed_year_and_on_is_caught(tmp_path, clock):
    yearly_log(tmp_path, clock, years=[2025, 2026])
    (tmp_path / "audit.jsonl").unlink()
    assert AuditLog(tmp_path / "audit.jsonl").verify().ok is False


def test_deleting_the_head_file_is_caught(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    record(log, 3)
    (tmp_path / "audit-head.json").unlink()
    _truncate(path, 2)
    assert AuditLog(path).verify().ok is False


def test_a_log_from_before_the_head_file_still_verifies_and_starts_one(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    record(log, 3)
    # As an existing log looks before this upgrade: no head file, no flag on any event
    lines = []
    prev = audit.GENESIS_HASH
    for line in path.read_text().splitlines():
        event = json.loads(line)
        event.pop("head_started", None)
        event["prev_hash"] = prev
        event["hash"] = audit._event_hash(event)
        prev = event["hash"]
        lines.append(json.dumps(event))
    path.write_text("\n".join(lines) + "\n")
    (tmp_path / "audit-head.json").unlink()

    upgraded = AuditLog(path)
    assert upgraded.verify().ok
    record(upgraded)
    assert upgraded.verify().ok
    assert json.loads((tmp_path / "audit-head.json").read_text())["seq"] == 4
    _truncate(path, 3)
    assert AuditLog(path).verify().ok is False


def test_a_crash_between_the_event_and_the_head_is_not_a_false_alarm(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    record(log, 2)
    head = (tmp_path / "audit-head.json").read_text()
    record(log)
    (tmp_path / "audit-head.json").write_text(head)  # as if it stopped before updating this
    reopened = AuditLog(path)
    assert reopened.verify().ok
    record(reopened)
    assert reopened.verify().ok


def test_the_head_is_encrypted_and_cant_be_swapped_for_a_plain_one(client):
    client.get("/api/claims")
    log = get_audit_log("meridian")
    head = org_folder() / "logs/audit-head.json"
    assert log.verify().ok
    raw = head.read_text()
    assert '"seq"' not in raw  # encrypted
    head.write_text(json.dumps({"seq": 1, "hash": "x"}))
    assert AuditLog(log.path, org_cipher_for("meridian")).verify().ok is False


def test_an_unreadable_head_doesnt_stop_the_log_loading(tmp_path):
    path = tmp_path / "audit.jsonl"
    record(AuditLog(path), 2)
    (tmp_path / "audit-head.json").write_text("not json")
    log = AuditLog(path)
    record(log)  # still records
    assert log.verify().ok is False
    assert (tmp_path / "audit-head.json").read_text() == "not json"


@pytest.mark.parametrize("junk", ["not json", "[1, 2]", '{"seq": 2}'])
def test_a_garbled_line_doesnt_stop_the_log_loading(tmp_path, junk):
    path = tmp_path / "audit.jsonl"
    record(AuditLog(path), 2)
    with path.open("a") as f:
        f.write(junk + "\n")
    log = AuditLog(path)
    assert log.verify().first_bad_seq == 3
    record(log)
    assert log.verify().ok is False
