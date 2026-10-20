"""The organisation wall: no route lets one organisation reach another's data.

Meridian's fixtures use ordinary IDs (CLM0000001, PAT000003, PROV001 …); Lakeside's use
their own ranges (CLM9000001, PAT900001, PROV901 …) and names, so anything of Lakeside's
showing up in a Meridian response is easy to spot, and vice versa.
"""

import json
import re

import pytest

from app.data.audit import get_audit_log
from app.data.orgs import get_org_registry
from app.data.users import get_user_store
from app.models import Role
from app.tests.conftest import LAKESIDE_FIXTURES_DIR, api_routes, sign_in
from app.tests.test_claim_entry import NEW_CLAIM

LAKESIDE_MARKERS = re.compile(r"CLM9\d{6}|PAT9\d{5}|PROV9\d\d|DEPT9\d|FAC9\d\d|Lakeside|admin2|biller2|analyst2")
MERIDIAN_MARKERS = re.compile(r"CLM000000\d|PAT00000\d|PROV00\d|FAC001|admin1|biller1|analyst1")


def lakeside_patient_names():
    rows = (LAKESIDE_FIXTURES_DIR / "dim_patients.csv").read_text().splitlines()[1:]
    return {f"{r.split(',')[1]} {r.split(',')[2]}" for r in rows}


def other_orgs_ids(client, org, role=Role.ADMIN):
    """IDs that exist in `org`: a claim, a patient, a saved draft, a custom rule, a user."""
    sign_in(client, role, org)
    claim_id = client.get("/api/claims", params={"page_size": 1}).json()["items"][0]["claim_id"]
    patient_id = client.get("/api/patients", params={"page_size": 1}).json()["items"][0]["patient_id"]
    draft_id = client.post("/api/drafts", json={"patient_id": patient_id}).json()["id"]
    rule = client.post("/api/rules", json={
        "name": "Org-only rule", "category": "Billing", "severity": "warning",
        "conditions": [{"field": "total_charge", "operator": "greaterThan", "value": "99999"}],
    }).json()
    return {
        "claim_id": claim_id,
        "patient_id": patient_id,
        "draft_id": draft_id,
        "rule_id": rule["id"],
        "username": "biller2" if org == "lakeside" else "biller1",
        "org_id": org,  # platform routes: refused to organisation accounts
        "grant_id": "EA-0000abcd",
    }


@pytest.mark.parametrize(("viewer", "owner"), [("meridian", "lakeside"), ("lakeside", "meridian")])
def test_no_route_reaches_another_organisations_records(client, viewer, owner):
    ids = other_orgs_ids(client, owner)
    sign_in(client, Role.ADMIN, viewer)
    # Anything of the owner's beyond the ID that was asked for would be a leak
    markers = LAKESIDE_MARKERS if owner == "lakeside" else MERIDIAN_MARKERS
    checked = 0
    for method, path in api_routes():
        params = re.findall(r"{(\w+)}", path)
        if not params:
            continue
        url = path
        for name in params:
            url = url.replace("{" + name + "}", ids[name])
        res = client.request(method, url, json={})
        checked += 1
        assert res.status_code in (403, 404, 422), f"{method} {url} -> {res.status_code}: {res.text[:200]}"
        echoed = res.text
        for asked in ids.values():
            echoed = echoed.replace(asked, "")
        leak = markers.search(echoed)
        assert leak is None, f"{method} {url} revealed {leak.group()}"
    assert checked >= 20  # every route with an ID in its path (a broken walk would find none)


def test_lists_and_dashboards_hold_only_the_organisations_own_data(client):
    other_orgs_ids(client, "lakeside")  # gives Lakeside a draft, a rule, and so on
    sign_in(client, Role.ADMIN, "meridian")
    names = lakeside_patient_names()
    for method, path in api_routes():
        if "{" in path or method != "GET" or path in ("/api/auth/logout",):
            continue
        res = client.get(path)
        if path.startswith("/api/platform/"):
            assert res.status_code == 403, f"an organisation admin reached GET {path}"
            continue
        assert res.status_code == 200, f"GET {path} -> {res.status_code}"
        leak = LAKESIDE_MARKERS.search(res.text)
        assert leak is None, f"GET {path} shows Lakeside's {leak.group()}"
        assert not any(name in res.text for name in names), f"GET {path} shows a Lakeside patient"

    sign_in(client, Role.ADMIN, "lakeside")
    for path in ("/api/claims", "/api/patients", "/api/dashboard", "/api/providers", "/api/facilities",
                 "/api/departments", "/api/drafts", "/api/rules", "/api/users", "/api/audit"):
        text = client.get(path).text
        leak = MERIDIAN_MARKERS.search(text)
        assert leak is None, f"Lakeside's GET {path} shows Meridian's {leak.group()}"
    assert client.get("/api/claims").json()["total"] == 10
    assert client.get("/api/auth/me").json()["organisation"] == {"id": "lakeside", "name": "Lakeside"}


def test_writes_stay_inside_the_organisation(client, today):
    # Meridian can't enter a claim for Lakeside's patient, or save a draft for one
    body = {**NEW_CLAIM, "patient_id": "PAT900001"}
    assert client.post("/api/claims", json=body).status_code == 422
    assert client.post("/api/drafts", json={"patient_id": "PAT900001"}).status_code == 422

    # A claim Meridian enters exists only in Meridian, IDs carrying on from Meridian's own
    created = client.post("/api/claims", json=NEW_CLAIM).json()["claim"]["claim_id"]
    assert created == "CLM0000005"
    sign_in(client, Role.ADMIN, "lakeside")
    assert client.get(f"/api/claims/{created}").status_code == 404
    assert client.get("/api/claims", params={"status": "Draft"}).json()["total"] == 0

    # Switching off a rule in Lakeside leaves Meridian's on
    client.patch("/api/rules/RULE-008", json={"enabled": False})
    sign_in(client, Role.ADMIN, "meridian")
    assert client.get("/api/rules/RULE-008").json()["enabled"] is True


def test_each_organisation_has_its_own_audit_log(client):
    client.get("/api/claims")
    sign_in(client, Role.BILLER, "lakeside")
    client.get("/api/claims")
    meridian = {e.username for e in get_audit_log("meridian").events()}
    lakeside = {e.username for e in get_audit_log("lakeside").events()}
    assert "admin1" in meridian and "biller2" not in meridian
    assert lakeside == {"biller2"}
    sign_in(client, Role.ADMIN, "lakeside")
    assert {e["username"] for e in client.get("/api/audit").json()} <= {"biller2", "admin2"}


def test_administrators_manage_only_their_own_organisations_accounts(client):
    usernames = {u["username"] for u in client.get("/api/users").json()}
    assert usernames == {"admin1", "biller1", "analyst1"}
    assert client.patch("/api/users/biller2", json={"active": False}).status_code == 404
    assert client.post("/api/users/biller2/password", json={"password": "Taken-over-123"}).status_code == 404
    # New accounts join the administrator's organisation, whatever the body says
    res = client.post("/api/users", json={
        "username": "newbie", "display_name": "New Bie", "role": "biller",
        "password": "New-biller-123", "organisation_id": "lakeside",
    })
    assert res.status_code == 201
    assert get_user_store().get("newbie").organisation_id == "meridian"
    # Usernames are unique across organisations, without saying whose a taken one is
    taken = client.post("/api/users", json={
        "username": "biller2", "display_name": "X", "role": "biller", "password": "New-biller-123",
    })
    assert taken.status_code == 409 and "lakeside" not in taken.text.lower()


def test_accounts_without_a_working_organisation_reach_nothing(client):
    store = get_user_store()
    # An account from before organisations (no organisation) can't use its session
    data = json.loads(store.path.read_text())
    for user in data["users"]:
        if user["username"] == "biller1":
            user.pop("organisation_id")
    store.path.write_text(json.dumps(data))
    sign_in(client, Role.BILLER)
    assert client.get("/api/claims").status_code == 401

    # A suspended organisation's accounts are refused too
    registry = get_org_registry()
    path = registry.root / "organisations.json"
    orgs = json.loads(path.read_text())
    for org in orgs["organisations"]:
        if org["id"] == "lakeside":
            org["status"] = "suspended"
    path.write_text(json.dumps(orgs))
    get_org_registry.cache_clear()
    sign_in(client, Role.ADMIN, "lakeside")
    assert client.get("/api/claims").status_code == 401
    sign_in(client, Role.ADMIN, "meridian")
    assert client.get("/api/claims").status_code == 200


def test_migrate_moves_a_single_organisation_install_into_meridian(anon_client, tmp_path, monkeypatch):
    from app import orgs as cli

    # A single-organisation install: files in backend/, accounts without an organisation
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    files = []
    for name in ("rules.json", "claim_corrections.json", "new_claims.json", "audit.jsonl"):
        (legacy / name).write_text("{}" if name.endswith(".json") else "")
        files.append(legacy / name)
    targets = ["rules.json", "claim_corrections.json", "new_claims.json", "logs/audit.jsonl"]
    monkeypatch.setattr(cli, "LEGACY_FILES", list(zip(files, targets)))
    monkeypatch.setattr(cli, "FIRST_ORG", ("acme", "Acme Health"))
    monkeypatch.setattr(cli, "DEFAULT_DATA_DIR", LAKESIDE_FIXTURES_DIR)
    get_user_store().add("oldtimer", "Old Timer", Role.BILLER, "Old-timer-pass-1")

    done = cli.migrate()
    assert "created organisation acme (Acme Health)" in done[0]
    folder = get_org_registry().folder("acme")
    assert all((folder / t).exists() for t in targets) and not any(f.exists() for f in files)
    assert get_user_store().get("oldtimer").organisation_id == "acme"
    assert get_user_store().get("admin1").organisation_id == "meridian"  # already assigned
    assert cli.migrate() == []  # safe to run twice
