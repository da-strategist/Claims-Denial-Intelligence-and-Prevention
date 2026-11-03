"""Administrators keep the organisation's 837 identifiers on screen, and a hospital that only
validates here never needs a clearinghouse."""

import json

from app.data.audit import get_audit_log
from app.models import AuditQuery, Role
from app.tests.conftest import org_folder, sign_in
from app.tests.test_claim_entry import create
from app.tests.test_claim_routes import hand_off
from app.tests.test_edi import LIVE_SETTINGS

URL = "/api/organisation/edi-settings"
NO_CLEARINGHOUSE = {**LIVE_SETTINGS, "receiver": {"id": "", "name": ""}}
ALL_FACILITIES = {"FAC001": "282111234", "FAC002": "282111234"}


def save(client, **settings):
    return client.put(URL, json=settings)


def test_settings_start_blank_and_say_what_each_route_needs(client):
    body = client.get(URL).json()
    assert body["settings"]["mode"] == "test"
    assert "submitter ID" in body["missing_for_handoff"]
    assert "clearinghouse name" not in body["missing_for_handoff"]
    assert "clearinghouse name" in body["missing_for_sending"]
    assert "ZIP+4 (9 digits) for Test Main Campus" in body["missing_for_handoff"]


def test_settings_save_tidied_and_survive(client):
    settings = {
        **LIVE_SETTINGS,
        "submitter": {**LIVE_SETTINGS["submitter"], "phone": "(704) 555-0100"},
        "billing_provider": {
            **LIVE_SETTINGS["billing_provider"],
            "tax_id": "56-1234567",
            "address": {"line1": "4200 Providence Rd", "city": "Charlotte", "state": "nc", "zip_code": "28211-1234"},
        },
        "facility_zip_codes": {"FAC001": "28211-1234", "FAC002": ""},
    }
    res = save(client, **settings)
    assert res.status_code == 200, res.text
    saved = client.get(URL).json()["settings"]
    assert saved["submitter"]["phone"] == "7045550100"
    assert saved["billing_provider"]["tax_id"] == "561234567"
    assert saved["billing_provider"]["address"]["state"] == "NC"
    assert saved["billing_provider"]["address"]["zip_code"] == "282111234"
    assert saved["facility_zip_codes"] == {"FAC001": "282111234"}
    assert json.loads((org_folder() / "edi_settings.json").read_text())["mode"] == "production"


def test_blanks_can_be_saved_but_wrong_values_cant(client):
    assert save(client, submitter={"name": "Meridian Billing"}).status_code == 200
    res = save(
        client,
        submitter={"id": "WAY-TOO-LONG-FOR-AN-ISA-FIELD", "phone": "123"},
        billing_provider={"npi": "1234567890", "tax_id": "12", "address": {"state": "Carolina", "zip_code": "28211"}},
        payer_ids={"PAY001": "BAD*ID", "PAY999": "X1"},
        facility_zip_codes={"FAC001": "28211", "FAC999": "282111234"},
    )
    assert res.status_code == 422
    detail = res.json()["detail"]
    for words in (
        "Submitter ID", "Submitter phone", "valid NPI", "tax ID", "state", "Billing provider ZIP+4",
        "payer ID for PAY001", "Unknown payer PAY999", "ZIP+4 for FAC001", "Unknown facility FAC999",
    ):
        assert words in detail
    # Nothing from the refused save was kept
    assert client.get(URL).json()["settings"]["submitter"]["name"] == "Meridian Billing"


def test_saving_is_audited_by_name_never_value(client):
    save(client, **LIVE_SETTINGS)
    events = get_audit_log("meridian").search(AuditQuery())
    event = next(e for e in events if e.action == "PUT /api/organisation/edi-settings")
    assert "billing_provider.tax_id" in event.detail["changed"]
    assert "payer_ids.PAY001" in event.detail["changed"]
    assert "561234567" not in str(event.detail)


def test_only_administrators_see_or_change_the_settings(client):
    for role in (Role.BILLER, Role.ANALYST):
        sign_in(client, role)
        assert client.get(URL).status_code == 403
        assert save(client, **LIVE_SETTINGS).status_code == 403
    sign_in(client, Role.PLATFORM)
    assert client.get(URL).status_code == 403


def test_each_organisation_has_its_own_settings(client):
    save(client, **LIVE_SETTINGS)
    sign_in(client, Role.ADMIN, org="lakeside")
    assert client.get(URL).json()["settings"]["submitter"]["id"] == ""


def test_a_hand_off_file_is_live_with_no_clearinghouse(client, today):
    res = save(client, **NO_CLEARINGHOUSE, facility_zip_codes=ALL_FACILITIES)
    assert res.status_code == 200, res.text
    assert res.json()["missing_for_handoff"] == []
    assert "clearinghouse name" in res.json()["missing_for_sending"]

    claim_id = create(client).json()["claim"]["claim_id"]
    hand_off(client, claim_id)
    summary = client.get(f"/api/claims/{claim_id}/handoff").json()["edi"]
    assert summary["test"] is False and summary["notes"] == []
    download = client.get(f"/api/claims/{claim_id}/handoff/837")
    assert f"{claim_id}_837P_handoff.txt" in download.headers["content-disposition"]
    isa = download.text.split("~")[0].split("*")
    assert isa[15] == "P"
    # Addressed to the hospital itself, with no placeholder left in the file
    assert isa[8].strip() == "SUB123"
    assert "NM1*40*2*MERIDIAN BILLING*****46*SUB123" in download.text
    assert "NOTSET" not in download.text
    assert "28211" + "1234" in download.text  # the facility's ZIP+4 from the settings


def test_sending_from_here_still_needs_a_clearinghouse(client, today):
    save(client, **NO_CLEARINGHOUSE, facility_zip_codes=ALL_FACILITIES)
    claim_id = create(client).json()["claim"]["claim_id"]
    edi = client.post(f"/api/claims/{claim_id}/submit").json()["claim"]["edi"]
    assert edi["test"] is True
    assert "clearinghouse" in edi["notes"][0]


def test_a_named_clearinghouse_stays_on_a_hand_off_file(client, today):
    save(client, **LIVE_SETTINGS, facility_zip_codes=ALL_FACILITIES)
    claim_id = create(client).json()["claim"]["claim_id"]
    hand_off(client, claim_id)
    assert "NM1*40*2*EXAMPLE CLEARINGHOUSE*****46*CLEARHOUSE1" in client.get(f"/api/claims/{claim_id}/handoff/837").text


def test_test_mode_keeps_a_complete_file_marked_as_test(client, today):
    save(client, **{**NO_CLEARINGHOUSE, "mode": "test"}, facility_zip_codes=ALL_FACILITIES)
    claim_id = create(client).json()["claim"]["claim_id"]
    hand_off(client, claim_id)
    summary = client.get(f"/api/claims/{claim_id}/handoff").json()["edi"]
    assert summary["test"] is True and summary["notes"] == ["Settings mode is test"]
