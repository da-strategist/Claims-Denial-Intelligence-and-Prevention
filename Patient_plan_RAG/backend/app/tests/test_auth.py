"""Accounts, sessions, sign-in throttling, password change, CSRF origin check."""

import os
import stat

import pytest
from fastapi.testclient import TestClient

from backend.app import main, users as users_cli
from backend.app.auth import sessions as auth_sessions
from backend.app.auth.users import Role, check_password_policy, hash_password, user_store, verify_password

PASSWORD = "correct horse battery"
NEW_PASSWORD = "another long passphrase"


@pytest.fixture
def member(data_dirs):
    return user_store.create("Member@Example.com", PASSWORD, Role.MEMBER, must_change_password=False)


def _login(client, username="member@example.com", password=PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


# ── Passwords and the user store ─────────────────────────────────────

def test_password_hash_roundtrip():
    stored = hash_password(PASSWORD)
    assert stored.startswith("scrypt$") and PASSWORD not in stored
    assert verify_password(PASSWORD, stored)
    assert not verify_password("wrong password!!", stored)
    assert not verify_password(PASSWORD, "garbage")
    assert hash_password(PASSWORD) != stored  # salted


def test_password_policy():
    assert check_password_policy("short") is not None
    assert check_password_policy(PASSWORD) is None


def test_create_user_rules_and_file_safety(data_dirs, member):
    assert member.username == "member@example.com"
    with pytest.raises(ValueError):
        user_store.create("member@example.com", PASSWORD, Role.MEMBER)  # duplicate
    with pytest.raises(ValueError):
        user_store.create("not-an-email", PASSWORD, Role.MEMBER)
    with pytest.raises(ValueError):
        user_store.create("x@example.com", "short", Role.MEMBER)
    text = user_store.path.read_text()
    assert PASSWORD not in text and "scrypt$" in text
    assert stat.S_IMODE(os.stat(user_store.path).st_mode) == 0o600


def test_disabled_user_cannot_authenticate(member):
    assert user_store.authenticate("member@example.com", PASSWORD)
    user_store.update("member@example.com", disabled=True)
    assert user_store.authenticate("member@example.com", PASSWORD) is None


# ── Sign in / out ────────────────────────────────────────────────────

def test_login_sets_safe_cookie_and_me_hides_hash(client, member):
    resp = _login(client)
    assert resp.status_code == 200
    cookie = resp.headers["set-cookie"]
    assert "ppr_session=" in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie
    me = client.get("/api/auth/me").json()
    assert me["username"] == "member@example.com" and me["role"] == "member"
    assert "password_hash" not in me


def test_wrong_password_and_unknown_user_look_the_same(client, member):
    a = _login(client, password="wrong password!!")
    b = _login(client, username="nobody@example.com")
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_me_requires_session(anon_client):
    assert anon_client.get("/api/auth/me").status_code == 401


def test_logout_ends_session(client, member):
    _login(client)
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401


def test_lockout_after_repeated_failures(client, member):
    for _ in range(auth_sessions.LOGIN_MAX_FAILURES):
        assert _login(client, password="wrong password!!").status_code == 401
    locked = _login(client)  # correct password, still locked
    assert locked.status_code == 429 and int(locked.headers["Retry-After"]) > 0


def test_success_resets_failure_count(client, member):
    for _ in range(auth_sessions.LOGIN_MAX_FAILURES - 1):
        _login(client, password="wrong password!!")
    assert _login(client).status_code == 200
    assert _login(client, password="wrong password!!").status_code == 401
    assert _login(client).status_code == 200


def test_idle_session_expires(client, member, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(auth_sessions.time, "monotonic", lambda: now[0])
    _login(client)
    now[0] += auth_sessions.SESSION_IDLE_SECONDS + 1
    assert client.get("/api/auth/me").status_code == 401


def test_disabling_a_user_ends_access_immediately(client, member):
    _login(client)
    user_store.update("member@example.com", disabled=True)
    assert client.get("/api/auth/me").status_code == 401


# ── Password change ──────────────────────────────────────────────────

def test_password_change_rules(client, member):
    _login(client)
    url = "/api/auth/password"
    assert client.post(url, json={"current_password": "wrong password!!",
                                  "new_password": NEW_PASSWORD}).status_code == 400
    assert client.post(url, json={"current_password": PASSWORD,
                                  "new_password": PASSWORD}).status_code == 400
    assert client.post(url, json={"current_password": PASSWORD,
                                  "new_password": "short"}).status_code == 400


def test_password_change_clears_flag_and_signs_out_other_sessions(client, data_dirs):
    user_store.create("new@example.com", PASSWORD, Role.MEMBER)  # must change by default
    other = TestClient(main.app)
    assert _login(other, "new@example.com").json()["must_change_password"] is True
    _login(client, "new@example.com")
    resp = client.post("/api/auth/password", json={"current_password": PASSWORD,
                                                   "new_password": NEW_PASSWORD})
    assert resp.status_code == 200 and resp.json()["must_change_password"] is False
    assert client.get("/api/auth/me").status_code == 200   # this browser keeps working
    assert other.get("/api/auth/me").status_code == 401    # other sessions signed out
    assert user_store.authenticate("new@example.com", NEW_PASSWORD)


# ── Cross-site requests ──────────────────────────────────────────────

def test_state_changing_request_from_other_site_is_refused(client, member):
    evil = client.post("/api/auth/login", headers={"Origin": "https://evil.example"},
                       json={"username": "member@example.com", "password": PASSWORD})
    assert evil.status_code == 403
    ok = client.post("/api/auth/login", headers={"Origin": "http://localhost:5174"},
                     json={"username": "member@example.com", "password": PASSWORD})
    assert ok.status_code == 200


# ── CLI ──────────────────────────────────────────────────────────────

def test_cli_add_assign_reset_list(data_dirs, capsys):
    assert users_cli.main(["add", "Admin@Example.com", "--role", "admin"]) == 0
    out = capsys.readouterr().out
    temp = out.split("sign-in): ")[1].strip()
    admin = user_store.get("admin@example.com")
    assert admin.role is Role.ADMIN and admin.must_change_password
    assert user_store.authenticate("admin@example.com", temp)

    assert users_cli.main(["add", "m@example.com", "--plans", "doc1"]) == 0
    assert users_cli.main(["assign", "m@example.com", "doc1", "doc2"]) == 0
    assert user_store.get("m@example.com").plan_ids == ["doc1", "doc2"]
    assert users_cli.main(["reset-password", "m@example.com"]) == 0
    assert users_cli.main(["list"]) == 0
    assert "m@example.com" in capsys.readouterr().out
    assert users_cli.main(["add", "m@example.com"]) == 1  # duplicate
