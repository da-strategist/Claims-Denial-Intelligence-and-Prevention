"""Who sees what: individuals, hospital staff, hospital admins, platform admin.

World: two hospitals (General, Mercy) with one patient each and a policy
uploaded for that patient; two individuals (Alice shares her policy with
General, Bob doesn't); the preloaded synthetic policy is a sample.
"""

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.auth.sessions import current_user, signed_in
from backend.app.auth.users import Role, user_store
from backend.app.services import records
from backend.app.tests.conftest import POLICY_PDF, TEST_PASSWORD, sign_in

SUMMIT = POLICY_PDF.parent / "summit_care_silver_hmo_2026.pdf"
OPEN_ROUTES = {"/api/health", "/api/auth/login", "/api/auth/logout", "/api/auth/register",
               "/api/auth/register/provider"}


# ── Every route is protected ─────────────────────────────────────────

def _depends_on(dependant, targets) -> bool:
    return any(d.call in targets or _depends_on(d, targets) for d in dependant.dependencies)


def _api_routes(routes):
    """Every APIRoute, including those inside included routers (newer FastAPI
    keeps them in a wrapper rather than copying them onto the app)."""
    for r in routes:
        if isinstance(r, APIRoute):
            yield r
        elif hasattr(r, "original_router"):
            yield from _api_routes(r.original_router.routes)


def test_every_api_route_requires_sign_in():
    routes = [r for r in _api_routes(main.app.routes) if r.path.startswith("/api")]
    assert len(routes) > 50  # the walk reached the routers, not just /api/health
    unprotected = [r.path for r in routes
                   if r.path not in OPEN_ROUTES and not _depends_on(r.dependant, {current_user, signed_in})]
    assert unprotected == []


@pytest.mark.parametrize("path", ["/api/policies", "/api/dashboard", "/api/admin/users",
                                  "/api/hospital/patients", "/api/shares"])
def test_anonymous_requests_get_401(anon_client, path):
    assert anon_client.get(path).status_code == 401


# ── The world ────────────────────────────────────────────────────────

def _upload(client, path, name, **form):
    with path.open("rb") as f:
        resp = client.post("/api/policies/upload", data=form,
                           files={"file": (name, f, "application/pdf")})
    assert resp.status_code == 200, resp.text
    return resp.json()["document_id"]


@pytest.fixture
def world(client, doc_id):
    if not SUMMIT.exists():
        pytest.skip("summit policy missing")
    general = records.orgs.add(records.Org(records.new_id(), "General Hospital"))
    mercy = records.orgs.add(records.Org(records.new_id(), "Mercy Medical"))
    w = {"admin": client, "sample": doc_id, "general": general.org_id, "mercy": mercy.org_id}
    w["gstaff"] = sign_in(TestClient(main.app), "gs@general.example", Role.HOSPITAL_STAFF, general.org_id)
    w["gadmin"] = sign_in(TestClient(main.app), "ga@general.example", Role.HOSPITAL_ADMIN, general.org_id)
    w["mstaff"] = sign_in(TestClient(main.app), "ms@mercy.example", Role.HOSPITAL_STAFF, mercy.org_id)
    w["alice"] = sign_in(TestClient(main.app), "alice@example.com")
    w["bob"] = sign_in(TestClient(main.app), "bob@example.com")

    w["p1"] = w["gstaff"].post("/api/hospital/patients", json={
        "name": "Pat One", "reference": "MRN-1", "date_of_birth": "1980-02-03"}).json()["patient_id"]
    w["p2"] = w["mstaff"].post("/api/hospital/patients", json={"name": "Pat Two"}).json()["patient_id"]
    w["gen_doc"] = _upload(w["gstaff"], SUMMIT, "p1_policy.pdf", patient_id=w["p1"])
    w["mercy_doc"] = _upload(w["mstaff"], SUMMIT, "p2_policy.pdf", patient_id=w["p2"])
    w["alice_doc"] = _upload(w["alice"], POLICY_PDF, "alice.pdf")
    w["bob_doc"] = _upload(w["bob"], POLICY_PDF, "bob.pdf")
    w["share"] = w["alice"].post("/api/shares", json={
        "document_id": w["alice_doc"], "org_id": general.org_id}).json()["share_id"]
    return w


def _ids(client):
    return {p["document_id"] for p in client.get("/api/policies").json()}


# ── Visibility ───────────────────────────────────────────────────────

def test_who_sees_which_documents(world):
    w = world
    assert _ids(w["admin"]) == {w["sample"]}
    assert _ids(w["alice"]) == {w["sample"], w["alice_doc"]}
    assert _ids(w["bob"]) == {w["sample"], w["bob_doc"]}
    assert _ids(w["gstaff"]) == {w["sample"], w["gen_doc"], w["alice_doc"]}
    assert _ids(w["gadmin"]) == _ids(w["gstaff"])
    assert _ids(w["mstaff"]) == {w["sample"], w["mercy_doc"]}


@pytest.mark.parametrize("suffix", ["", "/summary", "/chunks"])
def test_documents_you_cannot_see_look_missing(world, suffix):
    w = world
    denied = [("mstaff", "gen_doc"), ("mstaff", "alice_doc"), ("bob", "alice_doc"),
              ("alice", "gen_doc"), ("admin", "alice_doc"), ("admin", "gen_doc"),
              ("gstaff", "bob_doc"), ("gstaff", "mercy_doc")]
    for who, doc in denied:
        assert w[who].get(f"/api/policies/{w[doc]}{suffix}").status_code == 404, (who, doc)
    for who, doc in [("gstaff", "alice_doc"), ("alice", "alice_doc"), ("bob", "sample")]:
        assert w[who].get(f"/api/policies/{w[doc]}{suffix}").status_code == 200, (who, doc)


def test_upload_ownership(world):
    w = world
    gen = w["gstaff"].get(f"/api/policies/{w['gen_doc']}").json()
    assert (gen["org_id"], gen["patient_id"], gen["owner"]) == (w["general"], w["p1"], None)
    alice = w["alice"].get(f"/api/policies/{w['alice_doc']}").json()
    assert (alice["owner"], alice["org_id"]) == ("alice@example.com", None)
    sample = _upload(w["admin"], SUMMIT, "new_sample.pdf")  # platform admin uploads samples
    assert sample in _ids(w["bob"]) and sample in _ids(w["mstaff"])


def test_upload_rules(world):
    w = world
    with SUMMIT.open("rb") as f:
        no_patient = w["gstaff"].post("/api/policies/upload",
                                      files={"file": ("x.pdf", f, "application/pdf")})
    assert no_patient.status_code == 400
    with SUMMIT.open("rb") as f:
        other = w["gstaff"].post("/api/policies/upload", data={"patient_id": w["p2"]},
                                 files={"file": ("x.pdf", f, "application/pdf")})
    assert other.status_code == 404
    with SUMMIT.open("rb") as f:
        individual = w["alice"].post("/api/policies/upload", data={"patient_id": w["p1"]},
                                     files={"file": ("x.pdf", f, "application/pdf")})
    assert individual.status_code == 400


def test_dashboard_counts(world):
    w = world
    assert w["alice"].get("/api/dashboard").json()["total_policies"] == 2
    gs = w["gstaff"].get("/api/dashboard").json()
    # Pat One, plus the record created when Alice shared a policy
    assert (gs["total_policies"], gs["patient_count"]) == (3, 2)
    assert w["alice"].get("/api/dashboard").json()["patient_count"] is None


# ── Patient records ──────────────────────────────────────────────────

def test_patients_are_per_hospital(world):
    w = world
    general = [p for p in w["gstaff"].get("/api/hospital/patients").json()
               if not p["linked_username"]]  # leave out records created by sharing
    assert [p["patient_id"] for p in general] == [w["p1"]]
    assert {d["document_id"] for d in general[0]["documents"]} == {w["gen_doc"]}
    assert general[0]["reference"] == "MRN-1"
    assert w["mstaff"].get(f"/api/hospital/patients/{w['p1']}").status_code == 404
    for who in ("alice", "admin"):
        assert w[who].get("/api/hospital/patients").status_code == 403


def test_patient_record_validation(world):
    bad = world["gstaff"].post("/api/hospital/patients", json={"name": "X", "date_of_birth": "03/02/1980"})
    assert bad.status_code == 422


# ── Chat scope ───────────────────────────────────────────────────────

def _cited(client, **body):
    resp = client.post("/api/chat", json={"question": "What is the specialist copay?", **body})
    assert resp.status_code == 200, resp.text
    return {c["document_id"] for c in resp.json()["citations"]}


def test_hospital_chat_needs_a_patient_and_stays_on_them(world):
    w = world
    assert w["gstaff"].post("/api/chat", json={"question": "copay?"}).status_code == 400
    assert _cited(w["gstaff"], patient_id=w["p1"]) <= {w["gen_doc"]}
    assert w["mstaff"].post("/api/chat", json={"question": "copay?",
                                               "patient_id": w["p1"]}).status_code == 404
    assert w["alice"].post("/api/chat", json={"question": "copay?",
                                              "patient_id": w["p1"]}).status_code == 404


def test_individual_chat_searches_only_their_own_documents(world):
    w = world
    assert _cited(w["alice"]) <= {w["alice_doc"]}
    assert _cited(w["alice"], policy_id=w["sample"]) <= {w["sample"]}  # samples when chosen
    assert w["bob"].post("/api/chat", json={"question": "copay?",
                                            "policy_id": w["alice_doc"]}).status_code == 404


def test_conversations_stay_with_one_user_and_one_patient(world):
    w = world
    p1b = w["gstaff"].post("/api/hospital/patients", json={"name": "Pat Three"}).json()["patient_id"]
    first = w["gstaff"].post("/api/chat", json={"question": "Is MRI covered?",
                                                "patient_id": w["p1"]}).json()
    other_patient = w["gstaff"].post("/api/chat", json={
        "question": "Does it need approval?", "patient_id": p1b,
        "conversation_id": first["conversation_id"]}).json()
    assert other_patient["conversation_id"] != first["conversation_id"]
    colleague = w["gadmin"].post("/api/chat", json={
        "question": "Does it need approval?", "patient_id": w["p1"],
        "conversation_id": first["conversation_id"]}).json()
    assert colleague["conversation_id"] != first["conversation_id"]


# ── Sharing ──────────────────────────────────────────────────────────

def test_hospital_directory_lists_enabled_hospitals(world):
    w = world
    records.orgs.update(w["mercy"], disabled=True)
    names = [h["name"] for h in w["alice"].get("/api/shares/hospitals").json()]
    assert names == ["General Hospital"]


def test_sharing_rules(world):
    w = world
    for doc in ("bob_doc", "sample", "gen_doc"):  # only your own documents
        resp = w["alice"].post("/api/shares", json={"document_id": w[doc], "org_id": w["mercy"]})
        assert resp.status_code == 404, doc
    again = w["alice"].post("/api/shares", json={"document_id": w["alice_doc"], "org_id": w["general"]})
    assert again.json()["share_id"] == w["share"]  # sharing twice is idempotent
    assert [s["org_name"] for s in w["alice"].get("/api/shares").json()] == ["General Hospital"]
    assert w["gstaff"].post("/api/shares", json={"document_id": w["gen_doc"],
                                                 "org_id": w["mercy"]}).status_code == 403


def test_revoking_a_share_removes_access_immediately(world):
    w = world
    assert w["gstaff"].get(f"/api/policies/{w['alice_doc']}").status_code == 200
    assert w["bob"].delete(f"/api/shares/{w['share']}").status_code == 404  # not Bob's
    assert w["alice"].delete(f"/api/shares/{w['share']}").status_code == 200
    assert w["gstaff"].get(f"/api/policies/{w['alice_doc']}").status_code == 404


def test_hospital_files_a_shared_policy_under_a_patient(world):
    w = world
    shared = w["gstaff"].get("/api/hospital/shared").json()
    assert [(s["document_id"], s["shared_by"]) for s in shared] == [(w["alice_doc"], "alice@example.com")]
    assert w["mstaff"].patch(f"/api/hospital/shared/{w['share']}",
                             json={"patient_id": w["p2"]}).status_code == 404
    assert w["gstaff"].patch(f"/api/hospital/shared/{w['share']}",
                             json={"patient_id": w["p2"]}).status_code == 404  # Mercy's patient
    assert w["gstaff"].patch(f"/api/hospital/shared/{w['share']}",
                             json={"patient_id": w["p1"]}).status_code == 200
    docs = {d["document_id"] for d in w["gstaff"].get(f"/api/hospital/patients/{w['p1']}").json()["documents"]}
    assert docs == {w["gen_doc"], w["alice_doc"]}
    assert _cited(w["gstaff"], patient_id=w["p1"]) <= {w["gen_doc"], w["alice_doc"]}


# ── Hospital admins manage their own staff ───────────────────────────

def test_hospital_admin_manages_own_staff(world, anon_client):
    w = world
    created = w["gadmin"].post("/api/hospital/staff", json={"username": "New@General.example"}).json()
    assert (created["role"], created["org_id"], created["must_change_password"]) == \
        ("hospital_staff", w["general"], True)
    login = anon_client.post("/api/auth/login", json={"username": "new@general.example",
                                                      "password": created["temporary_password"]})
    assert login.status_code == 200
    staff = {u["username"] for u in w["gadmin"].get("/api/hospital/staff").json()}
    assert staff == {"gs@general.example", "ga@general.example", "new@general.example"}


def test_hospital_admin_cannot_touch_other_hospitals_or_promote_beyond_hospital(world):
    w = world
    assert w["gadmin"].patch("/api/hospital/staff/ms@mercy.example",
                             json={"disabled": True}).status_code == 404
    assert w["gadmin"].post("/api/hospital/staff", json={
        "username": "x@general.example", "role": "platform_admin"}).status_code == 400
    assert w["gstaff"].get("/api/hospital/staff").status_code == 403


def test_disabling_staff_signs_them_out(world):
    w = world
    w["gadmin"].patch("/api/hospital/staff/gs@general.example", json={"disabled": True})
    assert w["gstaff"].get("/api/policies").status_code == 401


# ── Platform admin ───────────────────────────────────────────────────

def test_platform_admin_onboards_a_hospital(world, anon_client):
    w = world
    resp = w["admin"].post("/api/admin/orgs", json={"name": "St. Luke's",
                                                    "admin_username": "Boss@StLukes.example"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["admin_username"] == "boss@stlukes.example"
    boss = user_store.get("boss@stlukes.example")
    assert (boss.role, boss.org_id, boss.must_change_password) == (Role.HOSPITAL_ADMIN, body["org_id"], True)
    login = anon_client.post("/api/auth/login", json={"username": "boss@stlukes.example",
                                                      "password": body["temporary_password"]})
    assert login.status_code == 200
    orgs = {o["name"]: o for o in w["admin"].get("/api/admin/orgs").json()}
    assert orgs["General Hospital"]["patient_count"] == 2  # incl. the one created by sharing


def test_duplicate_hospital_admin_creates_no_orphan_org(world):
    w = world
    before = len(records.orgs.all())
    resp = w["admin"].post("/api/admin/orgs", json={"name": "Dup", "admin_username": "alice@example.com"})
    assert resp.status_code == 400 and len(records.orgs.all()) == before


def test_disabling_a_hospital_signs_out_its_staff(world):
    w = world
    w["admin"].patch(f"/api/admin/orgs/{w['general']}", json={"disabled": True})
    assert w["gstaff"].get("/api/policies").status_code == 401
    assert w["mstaff"].get("/api/policies").status_code == 200


def test_only_platform_admin_uses_admin_endpoints(world):
    for who in ("alice", "gstaff", "gadmin"):
        assert world[who].get("/api/admin/orgs").status_code == 403
        assert world[who].get("/api/admin/users").status_code == 403


def test_admin_account_actions(world):
    w = world
    assert w["admin"].patch("/api/admin/users/admin@example.com",
                            json={"disabled": True}).status_code == 400
    temp = w["admin"].post("/api/admin/users/bob@example.com/reset-password").json()["temporary_password"]
    assert w["bob"].get("/api/policies").status_code == 401
    assert user_store.authenticate("bob@example.com", temp)


# ── Self sign-up ─────────────────────────────────────────────────────

def test_self_sign_up_creates_a_signed_in_individual(anon_client):
    resp = anon_client.post("/api/auth/register", json={
        "username": "New@Person.example", "password": "a long enough password", "role": "platform_admin"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "individual"  # the role field is ignored
    assert anon_client.get("/api/auth/me").json()["username"] == "new@person.example"
    assert anon_client.get("/api/policies").status_code == 200


def test_sign_up_rules(anon_client):
    ok = {"username": "x@example.com", "password": "a long enough password"}
    assert anon_client.post("/api/auth/register", json=ok).status_code == 200
    assert anon_client.post("/api/auth/register", json=ok).status_code == 400
    short = anon_client.post("/api/auth/register", json={"username": "y@example.com", "password": "short"})
    assert short.status_code == 400


def test_pending_password_change_blocks_data_routes(anon_client):
    user_store.create("temp@example.com", TEST_PASSWORD, Role.INDIVIDUAL)  # must change
    anon_client.post("/api/auth/login", json={"username": "temp@example.com",
                                              "password": TEST_PASSWORD})
    assert anon_client.get("/api/auth/me").status_code == 200
    assert anon_client.get("/api/policies").status_code == 403
