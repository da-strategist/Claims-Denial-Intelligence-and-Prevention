"""A pilot or production server runs real organisations only: they start from the shared
code sets (no sample patients or claims), never get generated patient details, and count
the Overview's periods back from today."""

import csv

import pytest

from app import orgs as cli
from app.data.orgs import get_org_registry
from app.data.registrations import get_registration_store
from app.models import Role
from app.sample_org import ORGANISATION_TABLES, SHARED_TABLES
from app.tests.conftest import FIXTURES_DIR, TestClient, sign_in
from app.tests.test_platform import new_org


def real(org_id="meridian"):
    """Treat a fixture organisation as a real one."""
    get_org_registry().set_sample_data(org_id, False)
    get_registration_store.cache_clear()


def test_a_real_organisation_gets_no_made_up_patient_details(client):
    assert client.get("/api/patients/PAT000001/registration").json()["source"] == "sample"
    real()
    res = client.get("/api/patients/PAT000001/registration")
    assert res.status_code == 404 and "Nothing on record" in res.json()["detail"]


def test_code_sets_hold_no_patients_providers_or_claims(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "DEFAULT_DATA_DIR", FIXTURES_DIR)
    out = tmp_path / "code_sets"
    assert cli.main(["code-sets", str(out)]) == 0
    assert cli.main(["code-sets", str(out)]) == 1  # never over an existing folder
    for table in SHARED_TABLES:
        assert (out / f"{table}.csv").read_text() == (FIXTURES_DIR / f"{table}.csv").read_text()
    for table in ORGANISATION_TABLES:
        rows = list(csv.reader((out / f"{table}.csv").open()))
        assert len(rows) == 1, f"{table} should have its header only"


def test_new_organisations_start_from_the_code_sets(client, tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "DEFAULT_DATA_DIR", FIXTURES_DIR)
    cli.main(["code-sets", str(tmp_path / "code_sets")])
    monkeypatch.setenv("RCM_CODE_SETS_DIR", str(tmp_path / "code_sets"))
    sign_in(client, Role.PLATFORM)
    assert new_org(client).status_code == 201
    acme = get_org_registry().get("acme")
    assert acme.sample_data is False
    data = get_org_registry().data_dir("acme")
    assert len(list(csv.reader((data / "fact_claims.csv").open()))) == 1


def test_production_never_copies_code_sets_from_another_organisation(client, monkeypatch):
    sign_in(client, Role.PLATFORM)
    monkeypatch.setenv("RCM_ENVIRONMENT", "production")
    res = new_org(client)
    assert res.status_code == 409 and "RCM_CODE_SETS_DIR" in res.json()["detail"]
    assert get_org_registry().get("acme") is None


def test_production_refuses_to_start_with_sample_organisations(anon_client, monkeypatch):
    monkeypatch.setenv("RCM_ENVIRONMENT", "production")
    monkeypatch.setenv("RCM_COOKIE_SECURE", "1")
    with pytest.raises(RuntimeError, match="sample organisations: lakeside, meridian"):
        with TestClient(anon_client.app):
            pass
    real("meridian")
    real("lakeside")
    with TestClient(anon_client.app) as started:
        assert started.get("/api/health").json()["demo"] is False


def test_the_sample_data_mark_is_set_from_the_command_line(anon_client):
    assert cli.main(["sample-data", "lakeside", "off"]) == 0
    assert get_org_registry().get("lakeside").sample_data is False
    assert cli.main(["sample-data", "nowhere", "on"]) == 1


def test_a_real_organisations_overview_counts_back_from_today(client, today):
    sample = client.get("/api/dashboard", params={"months": 1}).json()
    assert sample["period"] == {"start": "2025-03-01", "end": "2025-03-31"}  # the latest claim
    real()
    body = client.get("/api/dashboard", params={"months": 1}).json()
    assert body["period"] == {"start": "2026-01-01", "end": "2026-01-31"}  # today: 2026-01-10
    assert client.get("/api/auth/me").json()["organisation"]["sample_data"] is False


def test_the_health_check_says_whether_this_is_a_demo(anon_client):
    assert anon_client.get("/api/health").json()["demo"] is True
