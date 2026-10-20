"""The audit log: every API request recorded, tamper-evident, and readable by admins only."""

import json

from app.data.audit import AuditLog, get_audit_log, get_platform_audit_log
from app.models import Role
from app.tests.conftest import TEST_PASSWORD, sign_in
from app.tests.test_claim_entry import NEW_CLAIM


def events(client, **params):
    res = client.get("/api/audit", params=params)
    assert res.status_code == 200, res.text
    return res.json()


def test_requests_record_who_did_what_to_which_record(client):
    sign_in(client, Role.BILLER)
    client.get("/api/claims/CLM0000001")
    client.get("/api/claims", params={"search": "PAT000001", "page_size": 10})
    sign_in(client, Role.ADMIN)

    listing, view = events(client, username="biller1")  # newest first
    assert view["action"] == "GET /api/claims/{claim_id}"
    assert (view["records"], view["role"], view["outcome"]) == (
        {"claim_id": "CLM0000001"},
        "biller",
        "success",
    )
    assert listing["action"] == "GET /api/claims"
    assert listing["query"] == {"search": "PAT000001", "page_size": "10"}


def test_new_claims_record_the_patient_and_the_new_claim_id(client):
    client.post("/api/claims", json=NEW_CLAIM)
    (event,) = [e for e in events(client) if e["action"] == "POST /api/claims"]
    assert event["records"] == {"patient_id": "PAT000003", "claim_id": "CLM0000005"}
    assert event["status_code"] == 201


def test_fixes_and_assistant_questions_are_recorded(client):
    client.post("/api/aifix/CLM0000002/apply", json={"suggestion_id": "CLM0000002:RULE-008"})
    client.post("/api/assistant", json={"question": "Why was this denied?", "claim_id": "CLM0000002"})
    history = events(client, record_id="clm0000002")
    assert [e["action"] for e in history] == [
        "POST /api/assistant",
        "POST /api/aifix/{claim_id}/apply",
    ]
    assert history[0]["detail"] == {}  # the question itself isn't logged


def test_refusals_and_failed_sign_ins_are_recorded(anon_client):
    anon_client.get("/api/claims")
    anon_client.post("/api/auth/login", json={"username": "biller1", "password": "Nope-nope-123"})
    anon_client.post("/api/auth/login", json={"username": "admin1", "password": TEST_PASSWORD})
    anon_client.get("/api/claims/CLM9999999")  # not found
    sign_in(anon_client, Role.ANALYST)
    anon_client.get("/api/patients")

    # Signed-out requests belong to no organisation: the platform log has them
    platform = get_platform_audit_log().events()
    assert [(e.username, e.action, e.status_code) for e in platform] == [(None, "GET /api/claims", 401)]
    # Everything by (or aimed at) Meridian's accounts is in Meridian's own log
    log = get_audit_log("meridian").events()
    assert [(e.username, e.action, e.status_code, e.outcome) for e in log[:4]] == [
        ("biller1", "POST /api/auth/login", 401, "denied"),
        ("admin1", "POST /api/auth/login", 200, "success"),
        ("admin1", "GET /api/claims/{claim_id}", 404, "failed"),
        ("analyst1", "GET /api/patients", 403, "denied"),
    ]


def test_only_admins_read_the_audit_log_and_reading_it_is_recorded(client):
    sign_in(client, Role.BILLER)
    assert client.get("/api/audit").status_code == 403
    sign_in(client, Role.ADMIN)
    client.get("/api/audit")
    # A request is recorded once it's answered, so this read doesn't list itself
    latest = events(client, limit=2)
    assert [(e["username"], e["action"], e["status_code"]) for e in latest] == [
        ("admin1", "GET /api/audit", 200),
        ("biller1", "GET /api/audit", 403),
    ]


def test_health_checks_are_not_recorded(anon_client):
    anon_client.get("/api/health")
    assert get_audit_log("meridian").events() == []
    assert get_platform_audit_log().events() == []


def test_the_hash_chain_detects_edits_and_deletions(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    for n in range(1, 5):
        log.record(username="a", role=Role.ADMIN, action=f"GET /x/{n}", status_code=200)
    assert log.verify().model_dump() == {"ok": True, "events": 4, "first_bad_seq": None}
    assert path.stat().st_mode & 0o777 == 0o600

    # Reopening continues the chain
    AuditLog(path).record(username="a", role=Role.ADMIN, action="GET /x/5", status_code=200)
    assert AuditLog(path).verify().ok

    lines = path.read_text().splitlines()
    edited = json.loads(lines[2])
    edited["username"] = "someone-else"
    path.write_text("\n".join([*lines[:2], json.dumps(edited), *lines[3:]]) + "\n")
    assert AuditLog(path).verify().first_bad_seq == 3

    path.write_text("\n".join([lines[0], *lines[2:]]) + "\n")  # event 2 removed
    assert AuditLog(path).verify().first_bad_seq == 3


def test_verify_endpoint(client):
    client.get("/api/claims")
    assert client.get("/api/audit/verify").json()["ok"] is True
