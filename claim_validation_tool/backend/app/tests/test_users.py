"""The Users page API: administrators manage accounts, with safeguards and an audit trail."""

from fastapi.testclient import TestClient

from app.data.audit import get_audit_log
from app.main import app
from app.models import Role
from app.tests.conftest import sign_in

GOOD_PASSWORD = "New-user-pass-1"
OWN_PASSWORD = "Their-own-pass-2"


def add(client, username="amina", role="biller", password=GOOD_PASSWORD):
    return client.post(
        "/api/users",
        json={"username": username, "display_name": "Amina Bello", "role": role, "password": password},
    )


def login(username, password):
    with TestClient(app) as fresh:
        return fresh.post("/api/auth/login", json={"username": username, "password": password})


def change(client, current=GOOD_PASSWORD, new=OWN_PASSWORD):
    return client.post("/api/auth/password", json={"current_password": current, "new_password": new})


def first_sign_in(client, username, password=GOOD_PASSWORD):
    """Sign in with the password an administrator set, and replace it as required."""
    client.post("/api/auth/login", json={"username": username, "password": password})
    assert change(client, password).status_code == 200


def test_admins_add_users_who_can_then_sign_in(client):
    res = add(client)
    assert res.status_code == 201, res.text
    assert res.json()["role"] == "biller" and "password_hash" not in res.json()
    assert login("amina", GOOD_PASSWORD).json()["role"] == "biller"
    listed = {u["username"]: u for u in client.get("/api/users").json()}
    assert listed["amina"]["active"] is True and "admin1" in listed


def test_new_users_follow_the_rules(client):
    assert add(client, password="tooshort").status_code == 422
    assert add(client, password="alllowercaseletters").status_code == 422
    assert add(client, username="A B!").status_code == 422
    add(client)
    assert add(client).status_code == 409  # already exists


def test_roles_can_be_changed_and_apply_on_the_next_request(client):
    add(client)
    with TestClient(app) as amina:
        first_sign_in(amina, "amina")
        assert amina.get("/api/audit").status_code == 403  # billers can't read the audit log
        res = client.patch("/api/users/amina", json={"role": "admin"})
        assert res.json()["role"] == "admin"
        assert amina.get("/api/audit").status_code == 200  # no sign-out needed


def test_disabling_signs_the_person_out(client):
    add(client)
    with TestClient(app) as amina:
        amina.post("/api/auth/login", json={"username": "amina", "password": GOOD_PASSWORD})
        assert amina.get("/api/auth/me").status_code == 200
        client.patch("/api/users/amina", json={"active": False})
        assert amina.get("/api/auth/me").status_code == 401
    assert login("amina", GOOD_PASSWORD).status_code == 401
    client.patch("/api/users/amina", json={"active": True})
    assert login("amina", GOOD_PASSWORD).status_code == 200


def test_password_reset_signs_out_and_takes_the_new_password(client):
    add(client)
    with TestClient(app) as amina:
        amina.post("/api/auth/login", json={"username": "amina", "password": GOOD_PASSWORD})
        res = client.post("/api/users/amina/password", json={"password": "Another-pass-22"})
        assert res.status_code == 204
        assert amina.get("/api/auth/me").status_code == 401
    assert login("amina", GOOD_PASSWORD).status_code == 401
    assert login("amina", "Another-pass-22").status_code == 200
    assert client.post("/api/users/amina/password", json={"password": "weak"}).status_code == 422


def test_admins_cant_lock_themselves_or_everyone_out(client):
    # admin1 is the only administrator
    assert client.patch("/api/users/admin1", json={"role": "biller"}).status_code == 422
    assert client.patch("/api/users/admin1", json={"active": False}).status_code == 422
    assert client.patch("/api/users/admin1", json={"display_name": "Head of billing"}).status_code == 200

    # With a second admin, one can demote the other, but not the last one left
    add(client, username="second", role="admin")
    sign_in(client, Role.ADMIN)
    with TestClient(app) as second:
        first_sign_in(second, "second")
        assert second.patch("/api/users/admin1", json={"role": "biller"}).status_code == 200
        res = client.patch("/api/users/second", json={"active": False})
        assert res.status_code in (401, 403)  # admin1 is a biller now
    sign_in(client, Role.BILLER)
    assert client.get("/api/users").status_code == 403


def test_only_the_last_active_admin_is_protected(client):
    add(client, username="second", role="admin")
    client.patch("/api/users/second", json={"active": False})
    # second is disabled, so admin1 is again the only active admin
    res = client.patch("/api/users/second", json={"role": "biller"})
    assert res.status_code == 200  # demoting a disabled admin leaves admin1 in charge


def test_only_admins_manage_users_and_changes_are_audited(client):
    add(client)
    client.patch("/api/users/amina", json={"role": "analyst"})
    client.post("/api/users/amina/password", json={"password": "Another-pass-22"})
    events = [e for e in get_audit_log("meridian").events() if "/api/users" in e.action]
    assert [(e.action, e.records, e.detail) for e in events] == [
        ("POST /api/users", {}, {"new_user": "amina", "role": "biller"}),
        ("PATCH /api/users/{username}", {"username": "amina"}, {"role": "analyst"}),
        ("POST /api/users/{username}/password", {"username": "amina"}, {"password_reset": True}),
    ]
    assert "Another-pass-22" not in json_dump(get_audit_log("meridian").events())
    for role in (Role.BILLER, Role.ANALYST):
        sign_in(client, role)
        assert client.get("/api/users").status_code == 403
        assert add(client, username="sneaky").status_code == 403


def json_dump(events):
    return " ".join(e.model_dump_json() for e in events)


# ----- Temporary passwords -----------------------------------------------------------------


def test_a_new_account_must_choose_its_own_password_first(client):
    add(client)
    with TestClient(app) as amina:
        me = amina.post("/api/auth/login", json={"username": "amina", "password": GOOD_PASSWORD}).json()
        assert me["must_change_password"] is True
        assert amina.get("/api/auth/me").json()["must_change_password"] is True
        refused = amina.get("/api/claims")
        assert refused.status_code == 403 and "new password" in refused.json()["detail"]
        changed = change(amina)
        assert changed.status_code == 200 and changed.json()["must_change_password"] is False
        assert amina.get("/api/claims").status_code == 200  # carries on in the same session
    assert login("amina", GOOD_PASSWORD).status_code == 401
    assert login("amina", OWN_PASSWORD).json()["must_change_password"] is False
    assert {u["username"]: u for u in client.get("/api/users").json()}["amina"]["must_change_password"] is False


def test_changing_your_password_checks_the_current_one_and_the_policy(client):
    add(client)
    with TestClient(app) as amina:
        amina.post("/api/auth/login", json={"username": "amina", "password": GOOD_PASSWORD})
        assert change(amina, current="Wrong-pass-123").status_code == 403
        assert change(amina, new="weak").status_code == 422
        assert change(amina, new=GOOD_PASSWORD).status_code == 422  # the same one again
        assert amina.get("/api/claims").status_code == 403  # still temporary
    assert change(TestClient(app)).status_code == 401  # signed out


def test_wrong_current_passwords_lock_like_sign_in(client):
    add(client)
    with TestClient(app) as amina:
        amina.post("/api/auth/login", json={"username": "amina", "password": GOOD_PASSWORD})
        codes = [change(amina, current=f"Wrong-pass-{n:03d}").status_code for n in range(6)]
        assert codes[-1] == 429
        assert change(amina).status_code == 429  # even the right one, until the lock ends


def test_changing_your_password_ends_your_other_sessions(client):
    add(client)
    with TestClient(app) as phone, TestClient(app) as laptop:
        phone.post("/api/auth/login", json={"username": "amina", "password": GOOD_PASSWORD})
        laptop.post("/api/auth/login", json={"username": "amina", "password": GOOD_PASSWORD})
        assert change(laptop).status_code == 200
        assert phone.get("/api/auth/me").status_code == 401
        assert laptop.get("/api/auth/me").status_code == 200


def test_a_reset_by_an_administrator_is_temporary_but_your_own_isnt(client):
    add(client)
    with TestClient(app) as amina:
        first_sign_in(amina, "amina")
    client.post("/api/users/amina/password", json={"password": "Another-pass-22"})
    assert login("amina", "Another-pass-22").json()["must_change_password"] is True
    client.post("/api/users/admin1/password", json={"password": "Admin-own-pass-9"})
    assert client.get("/api/auth/me").json()["must_change_password"] is False


def test_password_changes_are_audited_without_the_password(client):
    add(client)
    with TestClient(app) as amina:
        first_sign_in(amina, "amina")
    event = [e for e in get_audit_log("meridian").events() if e.action == "POST /api/auth/password"][-1]
    assert event.username == "amina" and event.detail.get("password_changed") is True
    assert GOOD_PASSWORD not in event.model_dump_json() and OWN_PASSWORD not in event.model_dump_json()
