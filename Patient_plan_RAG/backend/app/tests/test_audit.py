"""Audit log: who accessed what, never content; tamper-evident chain."""

import json
import os
import stat

import pytest

from backend.app import audit
from backend.app.auth.users import Role, user_store
from backend.app.tests.conftest import TEST_PASSWORD

SECRET_QUESTION = "I have stage 2 diabetes, member ID W123456789 — is an MRI covered?"


def _entries(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_requests_are_recorded_with_identity_and_document(client, doc_id, isolated_audit_log):
    client.get(f"/api/policies/{doc_id}/summary")
    client.post("/api/chat", json={"question": SECRET_QUESTION, "policy_id": doc_id})
    client.post("/api/coverage/assess", json={"service_name": "MRI", "document_id": doc_id})
    entries = _entries(isolated_audit_log)
    summary = next(e for e in entries if e["route"] == "/api/policies/{document_id}/summary")
    assert (summary["user"], summary["role"], summary["document_id"], summary["status"]) == \
        ("admin@example.com", "admin", doc_id, 200)
    chat = next(e for e in entries if e["route"] == "/api/chat")
    assert chat["document_id"] == doc_id and chat["method"] == "POST"
    assess = next(e for e in entries if e["route"] == "/api/coverage/assess")
    assert assess["document_id"] == doc_id


def test_question_text_never_reaches_the_audit_log(client, doc_id, isolated_audit_log):
    client.post("/api/chat", json={"question": SECRET_QUESTION, "policy_id": doc_id})
    text = isolated_audit_log.read_text()
    for fragment in ("diabetes", "W123456789", "MRI covered"):
        assert fragment not in text


def test_sign_in_attempts_and_refusals_are_recorded(anon_client, isolated_audit_log):
    user_store.create("m@example.com", TEST_PASSWORD, Role.MEMBER, must_change_password=False)
    anon_client.post("/api/auth/login", json={"username": "M@example.com", "password": "wrong password!"})
    anon_client.get("/api/policies")
    anon_client.post("/api/auth/login", json={"username": "m@example.com", "password": TEST_PASSWORD})
    entries = _entries(isolated_audit_log)
    failed, anon, ok = entries[-3:]
    assert (failed["route"], failed["user"], failed["status"]) == ("/api/auth/login", "m@example.com", 401)
    assert (anon["route"], anon["user"], anon["status"]) == ("/api/policies", None, 401)
    assert (ok["user"], ok["status"]) == ("m@example.com", 200)
    assert "wrong password" not in isolated_audit_log.read_text()


def test_admin_actions_record_the_target_account(client, isolated_audit_log):
    client.post("/api/admin/users", json={"username": "New@Example.com"})
    client.post("/api/admin/users/new@example.com/reset-password")
    entries = _entries(isolated_audit_log)
    assert [e["target"] for e in entries[-2:]] == ["new@example.com", "new@example.com"]
    assert "temporary_password" not in isolated_audit_log.read_text()


def test_upload_records_the_new_document(client, isolated_audit_log):
    from backend.app.tests.conftest import POLICY_PDF
    with POLICY_PDF.open("rb") as f:
        new_id = client.post("/api/policies/upload",
                             files={"file": ("p.pdf", f, "application/pdf")}).json()["document_id"]
    assert _entries(isolated_audit_log)[-1]["document_id"] == new_id


def test_health_checks_are_not_recorded(anon_client, isolated_audit_log):
    before = len(_entries(isolated_audit_log)) if isolated_audit_log.exists() else 0
    anon_client.get("/api/health")
    after = len(_entries(isolated_audit_log)) if isolated_audit_log.exists() else 0
    assert after == before


# ── Chain integrity ──────────────────────────────────────────────────

@pytest.fixture
def log(tmp_path):
    path = tmp_path / "chain.log"
    for i in range(4):
        audit.record({"user": f"u{i}", "route": "/api/x", "status": 200}, path)
    return path


def test_chain_verifies_and_file_is_private(log):
    assert audit.verify(log) == (True, 4, "")
    assert stat.S_IMODE(os.stat(log).st_mode) == 0o600


@pytest.mark.parametrize("tamper", ["edit", "delete", "insert"])
def test_tampering_is_detected(log, tamper):
    lines = log.read_text().splitlines()
    if tamper == "edit":
        lines[1] = lines[1].replace('"u1"', '"someone-else"')
    elif tamper == "delete":
        del lines[2]
    else:
        lines.insert(2, lines[1])
    log.write_text("\n".join(lines) + "\n")
    ok, _, problem = audit.verify(log)
    assert not ok and "chain broken" in problem


def test_missing_or_empty_log_verifies(tmp_path):
    assert audit.verify(tmp_path / "none.log") == (True, 0, "")
    (tmp_path / "empty.log").write_text("")
    assert audit.verify(tmp_path / "empty.log") == (True, 0, "")


def test_cli_verify_exit_codes(log, monkeypatch, capsys):
    monkeypatch.setattr(audit, "AUDIT_FILE", log)
    assert audit.main(["verify"]) == 0 and "OK: 4" in capsys.readouterr().out
    log.write_text(log.read_text().replace('"u0"', '"x"'))
    assert audit.main(["verify"]) == 1 and "TAMPERED" in capsys.readouterr().out
    assert audit.main([]) == 2
