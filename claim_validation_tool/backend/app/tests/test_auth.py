"""Sign-in, sessions, and what each role may see and do."""

from datetime import timedelta

import pytest

from app.data.users import UserStore, get_user_store, hash_password, verify_password
from app.models import Role
from app.services import auth
from app.services.auth import SESSION_COOKIE, SessionStore
from app.tests.conftest import TEST_PASSWORD, sign_in
from app.tests.test_claim_entry import NEW_CLAIM


def login(client, username="admin1", password=TEST_PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


# --- Signing in and out --------------------------------------------------------------


def test_signed_out_requests_are_refused(anon_client):
    assert anon_client.get("/api/health").status_code == 200  # the only open route
    for path in ["/api/claims", "/api/claims/CLM0000001", "/api/dashboard", "/api/rules", "/api/auth/me"]:
        res = anon_client.get(path)
        assert res.status_code == 401, path
        assert res.json()["detail"] == "Sign in to continue"


def test_login_sets_an_http_only_session_cookie(anon_client):
    res = login(anon_client, "  Biller1 ")  # usernames are case-insensitive
    assert res.status_code == 200
    me = res.json()
    assert (me["username"], me["role"], me["idle_timeout_minutes"]) == ("biller1", "biller", 15)
    assert me["permissions"] == ["claims:read", "claims:write", "patients:read"]
    cookie = res.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    for flag in ["HttpOnly", "SameSite=strict", "Path=/api"]:
        assert flag in cookie
    assert anon_client.get("/api/auth/me").json()["username"] == "biller1"
    assert anon_client.get("/api/claims").status_code == 200


def test_wrong_password_or_unknown_user_get_the_same_answer(anon_client):
    for username, password in [("admin1", "Wrong-password-1"), ("nobody", TEST_PASSWORD)]:
        res = login(anon_client, username, password)
        assert (res.status_code, res.json()["detail"]) == (401, "Wrong username or password")
    assert anon_client.get("/api/claims").status_code == 401


def test_repeated_failures_lock_the_account(anon_client):
    for _ in range(5):
        assert login(anon_client, password="Wrong-password-1").status_code == 401
    res = login(anon_client)  # right password, but locked
    assert res.status_code == 429
    assert login(anon_client, "biller1").status_code == 200  # other accounts unaffected


def test_logout_ends_the_session(anon_client):
    login(anon_client)
    token = anon_client.cookies[SESSION_COOKIE]
    assert anon_client.post("/api/auth/logout").status_code == 204
    anon_client.cookies.set(SESSION_COOKIE, token)  # replaying the old cookie doesn't work
    assert anon_client.get("/api/claims").status_code == 401


def test_idle_and_overlong_sessions_expire(monkeypatch):
    sessions = SessionStore(idle=timedelta(minutes=15), max_age=timedelta(hours=8))
    start = auth._now()
    clock = {"now": start}
    monkeypatch.setattr(auth, "_now", lambda: clock["now"])

    active = sessions.create("a")
    for _ in range(40):  # used every 14 minutes: stays alive until 8 hours have passed
        clock["now"] += timedelta(minutes=14)
        if clock["now"] - start > timedelta(hours=8):
            assert sessions.touch(active) is None
            break
        assert sessions.touch(active) is not None

    idle = sessions.create("b")
    clock["now"] += timedelta(minutes=16)
    assert sessions.touch(idle) is None


def test_disabled_users_are_signed_out(client):
    assert client.get("/api/claims").status_code == 200
    get_user_store().update("admin1", active=False)
    assert client.get("/api/claims").status_code == 401
    assert login(client).status_code == 401


def test_role_changes_apply_to_live_sessions(client):
    get_user_store().update("admin1", role=Role.ANALYST)
    assert client.get("/api/auth/me").json()["role"] == "analyst"
    assert client.get("/api/patients").status_code == 403


# --- What each role may do ----------------------------------------------------------------


def test_analysts_see_claims_without_patient_details(client):
    sign_in(client, Role.ANALYST)
    claim = client.get("/api/claims/CLM0000001").json()
    assert claim["patient_id"] == "PAT000001"
    assert claim["patient"] is None
    for path in ["/api/claims", "/api/dashboard", "/api/aifix/CLM0000002", "/api/rules"]:
        assert client.get(path).status_code == 200, path


@pytest.mark.parametrize(
    ("method", "path", "body", "detail"),
    [
        ("get", "/api/patients", None, "view patient details"),
        ("post", "/api/claims", NEW_CLAIM, "change claims"),
        ("post", "/api/claims/CLM0000001/submit", None, "change claims"),
        ("post", "/api/aifix/CLM0000002/apply", {"suggestion_id": "CLM0000002:RULE-008"}, "change claims"),
        ("delete", "/api/aifix/CLM0000002/corrections", None, "change claims"),
        ("delete", "/api/rules/RULE-001", None, "change validation rules"),
        ("get", "/api/audit", None, "read the audit log"),
    ],
)
def test_analysts_cannot_change_anything(client, method, path, body, detail):
    sign_in(client, Role.ANALYST)
    res = client.request(method.upper(), path, json=body)
    assert res.status_code == 403
    assert res.json()["detail"] == f"Your role (analyst) can't {detail}"


def test_billers_work_claims_but_not_rules_or_the_audit_log(client):
    sign_in(client, Role.BILLER)
    assert client.get("/api/claims/CLM0000001").json()["patient"]["last_name"]
    assert client.get("/api/patients", params={"search": "Davis"}).status_code == 200
    assert client.post("/api/claims", json=NEW_CLAIM).status_code == 201
    assert client.patch("/api/rules/RULE-001", json={"enabled": False}).status_code == 403
    assert client.get("/api/audit").status_code == 403


def test_corrections_record_who_applied_them(client):
    sign_in(client, Role.BILLER)
    res = client.post(
        "/api/aifix/CLM0000002/apply", json={"suggestion_id": "CLM0000002:RULE-008"}
    )
    assert [c["applied_by"] for c in res.json()["applied"]] == ["biller1"]


# --- Accounts -----------------------------------------------------------------------------


def test_passwords_are_salted_scrypt_hashes():
    first, second = hash_password("Same-password-1"), hash_password("Same-password-1")
    assert first != second and first.startswith("scrypt$")
    assert verify_password("Same-password-1", first)
    assert not verify_password("same-password-1", first)


@pytest.mark.parametrize("password", ["Short-1", "alllowercase-123", "NoDigitsOrSymbols"])
def test_weak_passwords_are_refused(tmp_path, password):
    with pytest.raises(ValueError):
        UserStore(tmp_path / "users.json").add("carol", "Carol", Role.BILLER, password)


def test_user_file_is_private_and_holds_no_plain_passwords(tmp_path):
    path = tmp_path / "users.json"
    UserStore(path).add("carol", "Carol", Role.BILLER, "Carols-password-9")
    assert path.stat().st_mode & 0o777 == 0o600
    assert "Carols-password-9" not in path.read_text()
    assert UserStore(path).authenticate("carol", "Carols-password-9").role == Role.BILLER


def test_cli_adds_and_disables_accounts(anon_client, tmp_path, monkeypatch, capsys):
    from app import users as cli

    monkeypatch.setenv("RCM_USERS_FILE", str(tmp_path / "users.json"))
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: "Dana-password-42")
    get_user_store.cache_clear()
    try:
        assert cli.main(["add", "dana", "--name", "Dana Lee", "--role", "biller", "--org", "nowhere"]) == 1
        assert cli.main(["add", "dana", "--name", "Dana Lee", "--role", "biller", "--org", "meridian"]) == 0
        assert cli.main(["disable", "dana"]) == 0
        assert cli.main(["role", "nobody", "admin"]) == 1
        cli.main(["list"])
        assert "dana                 meridian       biller   disabled  Dana Lee" in capsys.readouterr().out
        assert get_user_store().authenticate("dana", "Dana-password-42") is None
    finally:
        get_user_store.cache_clear()


def test_every_api_route_requires_sign_in(anon_client):
    """Guards against a new router forgetting its permission check."""
    from app.tests.conftest import api_routes

    # Signing in itself: by password, or through the organisation's single sign-on
    open_routes = {"/api/health", "/api/auth/login", "/api/auth/sso/{org_id}/start", "/api/auth/sso/{org_id}/callback"}
    examples = {"claim_id": "CLM0000001", "rule_id": "RULE-001", "patient_id": "PAT000001",
                "draft_id": "DRF-0000abcd", "username": "admin1", "grant_id": "EA-0000abcd",
                "org_id": "meridian"}
    checked = 0
    for method, path in api_routes():
        if path in open_routes:
            continue
        concrete = path
        for name, value in examples.items():
            concrete = concrete.replace("{" + name + "}", value)
        assert "{" not in concrete, f"no example value for {path}"
        assert anon_client.request(method, concrete).status_code == 401, f"{method} {path}"
        checked += 1
    # A walk that silently finds no routes would pass; there are well over 40
    assert checked >= 40, f"only {checked} routes checked"
