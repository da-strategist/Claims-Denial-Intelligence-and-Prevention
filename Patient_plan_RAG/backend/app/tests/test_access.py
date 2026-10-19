"""Members see only their own plans; every API route requires sign-in."""

import shutil

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.auth.sessions import current_user
from backend.app.auth.users import Role, user_store
from backend.app.tests.conftest import POLICY_PDF, TEST_PASSWORD, sign_in

POLICY_DIR = POLICY_PDF.parent
OPEN_ROUTES = {"/api/health", "/api/auth/login", "/api/auth/logout"}


# ── Every route is protected ─────────────────────────────────────────

def _depends_on(dependant, target) -> bool:
    return any(d.call is target or _depends_on(d, target) for d in dependant.dependencies)


def test_every_api_route_requires_sign_in():
    unprotected = [
        r.path for r in main.app.routes
        if isinstance(r, APIRoute) and r.path.startswith("/api")
        and r.path not in OPEN_ROUTES and not _depends_on(r.dependant, current_user)
    ]
    assert unprotected == []


@pytest.mark.parametrize("method,path", [
    ("get", "/api/policies"), ("get", "/api/dashboard"), ("get", "/api/admin/users"),
])
def test_anonymous_requests_get_401(anon_client, method, path):
    assert getattr(anon_client, method)(path).status_code == 401


def test_anonymous_chat_gets_401(anon_client):
    assert anon_client.post("/api/chat", json={"question": "Is MRI covered?"}).status_code == 401


# ── Member scoping ───────────────────────────────────────────────────

@pytest.fixture
def world(client, data_dirs):
    """Admin client + two staff plans (Apex, Summit); member A is assigned
    Apex and has a private upload; member B has no plans."""
    summit = POLICY_DIR / "summit_care_silver_hmo_2026.pdf"
    if not summit.exists():
        pytest.skip("summit policy missing")
    with summit.open("rb") as f:
        summit_id = client.post("/api/policies/upload",
                                files={"file": (summit.name, f, "application/pdf")}).json()["document_id"]
    apex_id = next(p["document_id"] for p in client.get("/api/policies").json()
                   if p["filename"].startswith("apex"))
    a = sign_in(TestClient(main.app), "a@example.com", plan_ids=[apex_id])
    with POLICY_PDF.open("rb") as f:
        private_id = a.post("/api/policies/upload",
                            files={"file": ("my_policy.pdf", f, "application/pdf")}).json()["document_id"]
    b = sign_in(TestClient(main.app), "b@example.com")
    return {"admin": client, "a": a, "b": b, "apex": apex_id, "summit": summit_id,
            "private": private_id}


def _ids(client):
    return {p["document_id"] for p in client.get("/api/policies").json()}


def test_policy_lists_are_scoped(world):
    assert _ids(world["admin"]) == {world["apex"], world["summit"], world["private"]}
    assert _ids(world["a"]) == {world["apex"], world["private"]}
    assert _ids(world["b"]) == set()


def test_private_upload_is_owned_by_the_member(world):
    entry = world["admin"].get(f"/api/policies/{world['private']}").json()
    assert entry["owner"] == "a@example.com"
    summit = world["admin"].get(f"/api/policies/{world['summit']}").json()
    assert summit["owner"] is None


@pytest.mark.parametrize("suffix", ["", "/summary", "/chunks"])
def test_inaccessible_documents_look_missing(world, suffix):
    for who, doc in [("a", "summit"), ("b", "apex"), ("b", "private")]:
        resp = world[who].get(f"/api/policies/{world[doc]}{suffix}")
        assert resp.status_code == 404, (who, doc)
    assert world["a"].get(f"/api/policies/{world['private']}{suffix}").status_code == 200


def test_dashboard_counts_only_visible_policies(world):
    assert world["admin"].get("/api/dashboard").json()["total_policies"] == 3
    assert world["a"].get("/api/dashboard").json()["total_policies"] == 2
    assert world["b"].get("/api/dashboard").json()["total_policies"] == 0


def test_chat_without_policy_searches_only_your_documents(world):
    body = world["a"].post("/api/chat", json={"question": "What is the specialist copay?"}).json()
    assert {c["document_id"] for c in body["citations"]} <= {world["apex"], world["private"]}
    empty = world["b"].post("/api/chat", json={"question": "What is the specialist copay?"}).json()
    assert empty["confidence"] == "insufficient_evidence" and empty["citations"] == []


def test_chat_and_coverage_refuse_other_plans(world):
    assert world["b"].post("/api/chat", json={"question": "Is MRI covered?",
                                              "policy_id": world["apex"]}).status_code == 404
    for path in ("/api/coverage/assess", "/api/coverage/auth-checklist"):
        resp = world["a"].post(path, json={"service_name": "MRI", "document_id": world["summit"]})
        assert resp.status_code == 404
        ok = world["a"].post(path, json={"service_name": "MRI", "document_id": world["apex"]})
        assert ok.status_code == 200


def test_conversation_cannot_be_continued_by_another_user(world):
    first = world["a"].post("/api/chat", json={"question": "Is an MRI covered?",
                                               "policy_id": world["apex"]}).json()
    hijack = world["b"].post("/api/chat", json={"question": "Does it need approval?",
                                                "conversation_id": first["conversation_id"]}).json()
    assert hijack["conversation_id"] != first["conversation_id"]
    assert hijack["citations"] == []  # B has no plans, and none of A's context carried over


def test_revoked_plan_blocks_existing_conversation(world):
    first = world["a"].post("/api/chat", json={"question": "Is an MRI covered?",
                                               "policy_id": world["apex"]}).json()
    world["admin"].patch("/api/admin/users/a@example.com", json={"plan_ids": []})
    resp = world["a"].post("/api/chat", json={"question": "Does it need approval?",
                                              "conversation_id": first["conversation_id"]})
    assert resp.status_code == 404


# ── Roles and pending password change ────────────────────────────────

def test_members_cannot_use_admin_endpoints(world):
    assert world["a"].get("/api/admin/users").status_code == 403
    assert world["a"].post("/api/admin/users", json={"username": "x@example.com"}).status_code == 403


def test_pending_password_change_blocks_data_routes(anon_client):
    user_store.create("temp@example.com", TEST_PASSWORD, Role.MEMBER)  # must change
    anon_client.post("/api/auth/login", json={"username": "temp@example.com",
                                              "password": TEST_PASSWORD})
    assert anon_client.get("/api/auth/me").status_code == 200
    assert anon_client.get("/api/policies").status_code == 403


# ── Admin endpoints ──────────────────────────────────────────────────

def test_admin_creates_member_with_temporary_password(world, anon_client):
    resp = world["admin"].post("/api/admin/users", json={
        "username": "New@Example.com", "plan_ids": [world["summit"]]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["must_change_password"] and body["plan_ids"] == [world["summit"]]
    login = anon_client.post("/api/auth/login", json={"username": "new@example.com",
                                                      "password": body["temporary_password"]})
    assert login.status_code == 200 and login.json()["must_change_password"]


def test_admin_can_only_assign_existing_staff_plans(world):
    for bad in (["nosuchplan"], [world["private"]]):
        resp = world["admin"].patch("/api/admin/users/b@example.com", json={"plan_ids": bad})
        assert resp.status_code == 400
    ok = world["admin"].patch("/api/admin/users/b@example.com", json={"plan_ids": [world["summit"]]})
    assert ok.status_code == 200
    assert _ids(world["b"]) == {world["summit"]}


def test_disable_and_reset_sign_the_user_out(world):
    world["admin"].patch("/api/admin/users/a@example.com", json={"disabled": True})
    assert world["a"].get("/api/policies").status_code == 401
    world["admin"].patch("/api/admin/users/a@example.com", json={"disabled": False})
    sign_in(world["a"], "a@example.com")
    temp = world["admin"].post("/api/admin/users/a@example.com/reset-password").json()["temporary_password"]
    assert world["a"].get("/api/policies").status_code == 401
    assert user_store.get("a@example.com").must_change_password
    assert user_store.authenticate("a@example.com", temp)


def test_admin_cannot_disable_themselves(world):
    resp = world["admin"].patch("/api/admin/users/admin@example.com", json={"disabled": True})
    assert resp.status_code == 400
