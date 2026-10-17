"""The 837 claim file: created at submission from what the claim captured, saved, and
downloadable by roles that change claims; plus the patient registration it's filled from."""

import json
from datetime import date

import pytest

from app.data import repository
from app.data.audit import get_audit_log
from app.data.new_claims import get_new_claim_store
from app.data.registrations import get_registration_store
from app.models import Role
from app.tests.conftest import org_folder, sign_in, use_data_dir
from app.tests.test_claim_entry import NEW_CLAIM, create

LIVE_SETTINGS = {
    "mode": "production",
    "submitter": {"id": "SUB123", "name": "Meridian Billing", "contact_name": "Ann Lee", "phone": "7045550100"},
    "receiver": {"id": "CLEARHOUSE1", "name": "Example Clearinghouse"},
    "billing_provider": {
        "name": "Meridian Regional Medical Center",
        "npi": "1234567893",  # passes the NPI check digit
        "tax_id": "561234567",
        "address": {"line1": "4200 Providence Rd", "city": "Charlotte", "state": "NC", "zip_code": "282111234"},
    },
    "payer_ids": {"PAY001": "MCR01", "PAY002": "BCBSNC"},
}


def submitted_837(client, **changes):
    claim_id = create(client, **changes).json()["claim"]["claim_id"]
    res = client.post(f"/api/claims/{claim_id}/submit")
    assert res.status_code == 200, res.text
    download = client.get(f"/api/claims/{claim_id}/837")
    assert download.status_code == 200, download.text
    return res.json()["claim"], download


def segments(text):
    return [segment.strip() for segment in text.split("~") if segment.strip()]


def find(segs, prefix):
    return [s for s in segs if s.startswith(prefix + "*")]


def test_a_five_digit_facility_zip_keeps_it_a_test_file(client, today):
    (org_folder() / "edi_settings.json").write_text(json.dumps(LIVE_SETTINGS))
    claim, _ = submitted_837(client)
    assert claim["edi"]["test"] is True
    assert claim["edi"]["notes"] == ["Not set: ZIP+4 (9 digits) for Test Main Campus"]


def test_a_professional_claim_is_submitted_with_an_837p(client, today):
    claim, download = submitted_837(client)
    segs = segments(download.text)
    assert claim["edi"]["transaction"] == "837P"
    assert download.headers["content-disposition"] == f'attachment; filename="{claim["claim_id"]}_837P_TEST.txt"'

    # Envelope: fixed-width ISA, test file until the settings are filled in
    isa = segs[0]
    assert len(isa) == 105 and isa.split("*")[15] == "T"
    assert find(segs, "GS")[0].endswith("*X*005010X222A1")
    st, se = find(segs, "ST")[0], find(segs, "SE")[0]
    assert st == "ST*837*0001*005010X222A1"
    assert se == f"SE*{segs.index(se) - segs.index(st) + 1}*0001"  # counts ST..SE
    assert claim["edi"]["test"] is True and "billing provider NPI" in claim["edi"]["notes"][0]

    # The claim, as captured: patient is the policy holder, Medicare Part B
    assert "SBR*P*18*******MB" in segs
    assert "NM1*IL*1*DAVIS*DONALD****MI*MBR123456" in segs
    assert "N3*12 OAK ST" in segs and "N4*CHARLOTTE*NC*28205" in segs
    assert "DMG*D8*19760502*M" in segs
    assert f"CLM*{claim['claim_id']}*95***11:B:1*Y*A*Y*Y" in segs
    assert "HI*ABK:E1165" in segs
    assert find(segs, "NM1*82")[0] == "NM1*82*1*ONE*TEST****XX*1000000001"  # rendering provider
    assert "SV1*HC:99213*95*UN*1***1" in segs
    assert "DTP*472*D8*20260105" in segs


def test_live_settings_make_a_production_file(client, today, tmp_path, monkeypatch):
    # The facility's address needs ZIP+4 too
    facilities = tmp_path / "data"
    import shutil

    from app.tests.conftest import FIXTURES_DIR

    shutil.copytree(FIXTURES_DIR, facilities)
    csv = facilities / "dim_facilities.csv"
    csv.write_text(csv.read_text().replace("NC 28211", "NC 282111234"))
    use_data_dir("meridian", facilities)
    (org_folder() / "edi_settings.json").write_text(json.dumps(LIVE_SETTINGS))
    claim, download = submitted_837(client)
    segs = segments(download.text)
    assert claim["edi"]["test"] is False and claim["edi"]["notes"] == []
    assert segs[0].split("*")[15] == "P"
    assert segs[0].split("*")[6] == "SUB123".ljust(15)
    assert "NM1*85*2*MERIDIAN REGIONAL MEDICAL CENTER*****XX*1234567893" in segs
    assert "REF*EI*561234567" in segs
    assert "NM1*PR*2*MEDICARE FFS*****PI*MCR01" in segs
    assert download.headers["content-disposition"].endswith('_837P.txt"')


def test_control_numbers_never_repeat(client, today):
    first, _ = submitted_837(client)
    second, _ = submitted_837(client)
    assert int(second["edi"]["control_number"]) == int(first["edi"]["control_number"]) + 1


def test_an_institutional_claim_gets_an_837i(client, today):
    billing = {
        **NEW_CLAIM["billing"],
        "institutional": {"type_of_bill": "131", "admission_type": "3", "admission_source": "1", "patient_status": "01"},
    }
    lines = [{"cpt_code": "99213", "icd10_pointer": "E11.65", "revenue_code": "0510"}]
    claim, download = submitted_837(client, claim_type="Institutional", billing=billing, lines=lines)
    segs = segments(download.text)
    assert claim["edi"]["transaction"] == "837I"
    assert find(segs, "ST")[0] == "ST*837*0001*005010X223A2"
    assert f"CLM*{claim['claim_id']}*95***13:A:1**A*Y*Y" in segs
    assert "DTP*434*RD8*20260105-20260105" in segs
    assert "CL1*3*1*01" in segs
    assert find(segs, "NM1*71")[0] == "NM1*71*1*ONE*TEST****XX*1000000001"  # attending provider
    assert "SV2*0510*HC:99213*95*UN*1" in segs


def test_a_dependent_patient_and_other_coverage(client, today):
    billing = {
        **NEW_CLAIM["billing"],
        "policy": {
            "member_id": "BCX987",
            "group_number": "G-55",
            "relationship": "spouse",
            "first_name": "Maria",
            "last_name": "Davis",
            "birth_date": "1974-02-11",
            "sex": "F",
        },
        "other_policies": [{"member_id": "MCR555"}],
    }
    claim, download = submitted_837(client, payer_id="PAY002", other_payer_ids=["PAY001"], billing=billing)
    segs = segments(download.text)
    # Subscriber is the spouse; the patient gets their own loop
    assert "HL*2*1*22*1" in segs and "SBR*P**G-55******CI" in segs
    assert "NM1*IL*1*DAVIS*MARIA****MI*BCX987" in segs
    assert "HL*3*2*23*0" in segs and "PAT*01" in segs
    assert "NM1*QC*1*DAVIS*DONALD" in segs
    # Medicare as secondary coverage, held by the patient
    assert "SBR*S*18*******MB" in segs and "OI***Y*P**Y" in segs
    assert "NM1*IL*1*DAVIS*DONALD****MI*MCR555" in segs


def test_self_pay_needs_no_policy_and_no_837(client, today):
    billing = {k: v for k, v in NEW_CLAIM["billing"].items() if k != "policy"}
    claim_id = create(client, payer_id="PAY010", billing=billing).json()["claim"]["claim_id"]
    res = client.post(f"/api/claims/{claim_id}/submit")
    assert res.status_code == 200, res.text
    assert res.json()["claim"]["edi"] is None
    assert client.get(f"/api/claims/{claim_id}/837").status_code == 404


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"billing": {**NEW_CLAIM["billing"], "policy": None}}, "Give the member ID for Medicare FFS"),
        ({"other_payer_ids": ["PAY002"], "billing": NEW_CLAIM["billing"]}, "policy details for each other payer"),
        ({"claim_type": "Institutional"}, "Institutional claims need the type of bill"),
        (
            {"billing": {**NEW_CLAIM["billing"], "policy": {"member_id": "X1", "relationship": "child"}}},
            "give the holder's first_name, last_name, birth_date, sex",
        ),
        (
            {"billing": {**NEW_CLAIM["billing"], "patient_address": {"line1": "1 A St", "city": "Charlotte", "state": "nc", "zip_code": "28205"}}},
            "state",
        ),
    ],
)
def test_claims_without_what_the_837_needs_are_refused(client, changes, message):
    res = create(client, **changes)
    assert res.status_code == 422
    assert message in json.dumps(res.json())


def test_only_roles_that_change_claims_download_and_its_audited(client, today):
    claim, _ = submitted_837(client)
    events = [e for e in get_audit_log("meridian").events() if e.action.endswith("/837")]
    assert (events[-1].username, events[-1].detail) == ("admin1", {"export": "837P"})
    sign_in(client, Role.ANALYST)
    assert client.get(f"/api/claims/{claim['claim_id']}/837").status_code == 403
    # Analysts don't see the billing details either
    assert client.get(f"/api/claims/{claim['claim_id']}").json()["billing"] is None


def test_the_837_survives_a_restart(client, today):
    claim, download = submitted_837(client)
    for cache in (repository.get_repository, get_new_claim_store):
        cache.cache_clear()
    again = client.get(f"/api/claims/{claim['claim_id']}/837")
    assert again.text == download.text
    assert client.get(f"/api/claims/{claim['claim_id']}").json()["edi"] == claim["edi"]


# --- Registration: what selecting a patient fills in ---------------------------


def test_sample_patients_get_consistent_generated_details(client, today):
    first = client.get("/api/patients/PAT000003/registration").json()
    assert first == client.get("/api/patients/PAT000003/registration").json()  # same every time
    assert first["source"] == "sample"
    patient = client.get("/api/patients/PAT000003").json()
    born = date.fromisoformat(first["birth_date"])
    age = today_age(born, repository._today())
    assert age == patient["age"]
    assert first["address"]["zip_code"] == patient["zip_code"]
    assert first["policies"]["PAY001"]["member_id"].startswith("POL001")


def today_age(born, on):
    return on.year - born.year - ((on.month, on.day) < (born.month, born.day))


def test_a_claim_updates_the_patients_registration(client, today):
    create(client)
    registration = client.get("/api/patients/PAT000003/registration").json()
    assert registration["source"] == "entered" and registration["updated_by"] == "admin1"
    assert registration["birth_date"] == "1976-05-02"
    assert registration["address"]["line1"] == "12 Oak St"
    assert registration["policies"]["PAY001"]["member_id"] == "MBR123456"
    # Kept across restarts, readable only by the API's account
    get_registration_store.cache_clear()
    assert client.get("/api/patients/PAT000003/registration").json() == registration
    sign_in(client, Role.ANALYST)
    assert client.get("/api/patients/PAT000003/registration").status_code == 403


# --- PDFs built from the saved 837 --------------------------------------------------


def pdf_text(response):
    from io import BytesIO

    from pypdf import PdfReader

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    return " ".join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)


def test_a_professional_claim_prints_on_a_cms1500_layout(client, today):
    claim, _ = submitted_837(client)
    res = client.get(f"/api/claims/{claim['claim_id']}/claim-form.pdf")
    assert res.headers["content-disposition"] == f'attachment; filename="{claim["claim_id"]}_CMS-1500_TEST.pdf"'
    text = pdf_text(res)
    for expected in (
        "HEALTH INSURANCE CLAIM FORM",
        "1a. INSURED'S I.D. NUMBER", "MBR123456",
        "DAVIS, DONALD", "1976-05-02",
        "A. E11.65",
        "99213", "$95.00",
        "26. PATIENT'S ACCOUNT NO.", claim["claim_id"],
        "TEST FILE",
    ):
        assert expected in text, expected


def test_an_institutional_claim_prints_on_a_ub04_layout(client, today):
    billing = {
        **NEW_CLAIM["billing"],
        "institutional": {"type_of_bill": "131", "admission_type": "3", "admission_source": "1", "patient_status": "01"},
    }
    lines = [{"cpt_code": "99213", "icd10_pointer": "E11.65", "revenue_code": "0510"}]
    claim, _ = submitted_837(client, claim_type="Institutional", billing=billing, lines=lines)
    text = pdf_text(client.get(f"/api/claims/{claim['claim_id']}/claim-form.pdf"))
    for expected in ("UB-04 CLAIM FORM", "4. TYPE OF BILL", "0131", "0510", "Clinic", "67. PRINCIPAL DIAGNOSIS", "E11.65"):
        assert expected in text, expected


def test_the_readable_837_names_each_part_and_includes_the_raw_file(client, today):
    claim, download = submitted_837(client)
    res = client.get(f"/api/claims/{claim['claim_id']}/837-readable.pdf")
    assert res.headers["content-disposition"].endswith('_837P_readable_TEST.pdf"')
    text = pdf_text(res)
    for expected in (
        "Billing provider (2010AA)", "Subscriber (2000B", "Payer (2010BB)", "Claim (2300)",
        "Service lines (2400)", "Medicare Part B", "SBR09", "Test file (ISA15 = T)",
        "The file as sent", f"CLM*{claim['claim_id']}*95",
    ):
        assert expected in text, expected


def test_pdfs_need_a_submitted_claim_and_a_role_that_changes_claims(client, today):
    draft_id = create(client).json()["claim"]["claim_id"]
    assert client.get(f"/api/claims/{draft_id}/claim-form.pdf").status_code == 404
    claim, _ = submitted_837(client)
    client.get(f"/api/claims/{claim['claim_id']}/claim-form.pdf")
    exports = [e.detail.get("export") for e in get_audit_log("meridian").events() if e.action.endswith(".pdf")]
    assert exports[-1] == "CMS-1500 PDF"
    sign_in(client, Role.ANALYST)
    for path in ("claim-form.pdf", "837-readable.pdf"):
        assert client.get(f"/api/claims/{claim['claim_id']}/{path}").status_code == 403
