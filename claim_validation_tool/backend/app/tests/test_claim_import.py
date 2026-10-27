"""Uploading claims: a CSV/Excel file in the template's layout, or an X12 837, read into
Draft claims that are validated like claims typed into the form."""

import base64
import io

import pandas as pd

from app.data.audit import get_audit_log
from app.models import Role
from app.tests.conftest import sign_in
from app.tests.test_claim_entry import NEW_CLAIM
from app.tests.test_edi import segments, submitted_837

HEADER = "claim_ref,patient_id,payer_id,provider_id,service_date,diagnoses,cpt_code,icd10_pointer,units,member_id"


def upload(client, content: str | bytes, filename="claims.csv"):
    data = content.encode() if isinstance(content, str) else content
    return client.post(
        "/api/claims/import", json={"filename": filename, "content": base64.b64encode(data).decode()}
    )


def csv_file(*rows: str) -> str:
    return "\n".join([HEADER, *rows]) + "\n"


def test_the_template_downloads_and_uploads_as_is(client, today):
    template = client.get("/api/claims/import/template.csv")
    assert template.status_code == 200
    assert template.headers["content-type"].startswith("text/csv")
    assert template.text.splitlines()[0].startswith("claim_ref,patient_id,payer_id,provider_id")
    res = upload(client, template.text)
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["file_type"], body["claims_found"], body["failed"]) == ("csv", 1, [])
    [created] = body["created"]
    assert (created["ref"], created["where"]) == ("A1", "rows 2, 3")


def test_rows_are_grouped_into_draft_claims_and_validated(client, today):
    res = upload(
        client,
        csv_file(
            "A,PAT000003,PAY001,PROV001,2026-01-05,E11.65|I10,99213,E11.65,1,MBR123456",
            "A,,,,,,99214,I10,2,",
            "B,PAT000003,PAY001,PROV001,01/06/2026,E11.65,99213,,1,MBR123456",
        ),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["claims_found"] == 2 and body["failed"] == []
    first, second = body["created"]
    assert first["claim"]["claim_id"] == "CLM0000005"
    assert first["claim"]["status"] == "Draft"
    assert (first["claim"]["primary_icd10"], first["claim"]["additional_icd10"]) == ("E11.65", ["I10"])
    assert first["claim"]["total_charge"] == 95.0 + 2 * 150.0  # standard charges × units
    assert first["validation"]["claim_id"] == first["claim"]["claim_id"]
    assert second["claim"]["service_date"] == "2026-01-06"
    # The blank pointer went to the primary diagnosis; the claim is a normal Draft
    detail = client.get(f"/api/claims/{second['claim']['claim_id']}").json()
    assert [line["icd10_pointer"] for line in detail["lines"]] == ["E11.65"]
    assert detail["billing"]["policy"]["member_id"] == "MBR123456"
    drafts = client.get("/api/claims", params={"status": "Draft"}).json()["items"]
    assert {c["claim_id"] for c in drafts} >= {first["claim"]["claim_id"], second["claim"]["claim_id"]}


def test_billing_details_left_blank_come_from_the_registration(client, today):
    registration = client.get("/api/patients/PAT000003/registration").json()
    res = upload(client, csv_file("A,PAT000003,PAY001,PROV001,2026-01-05,E11.65,99213,,,"))
    [created] = res.json()["created"]
    detail = client.get(f"/api/claims/{created['claim']['claim_id']}").json()
    assert detail["billing"]["patient_birth_date"] == registration["birth_date"]
    assert detail["billing"]["patient_address"] == {**registration["address"]}
    assert detail["billing"]["policy"]["member_id"] == registration["policies"]["PAY001"]["member_id"]


def test_bad_claims_are_reported_and_the_rest_are_saved(client, today):
    res = upload(
        client,
        csv_file(
            "OK,PAT000003,PAY001,PROV001,2026-01-05,E11.65,99213,,1,MBR1",
            "NOPAT,PAT999999,PAY001,PROV001,2026-01-05,E11.65,99213,,1,MBR1",
            "BADCPT,PAT000003,PAY001,PROV001,2026-01-05,E11.65,00000,,1,MBR1",
            "MIXED,PAT000003,PAY001,PROV001,2026-01-05,E11.65,99213,,1,MBR1",
            "MIXED,PAT000003,PAY002,,,,99214,,1,",
            "NODX,PAT000003,PAY001,PROV001,2026-01-05,E11.65|I10,99213,E11.65,1,MBR1",
            "BADDATE,PAT000003,PAY001,PROV001,soon,E11.65,99213,,1,MBR1",
            ",PAT000003,PAY001,PROV001,2026-01-05,E11.65,99213,,1,MBR1",
        ),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert [c["ref"] for c in body["created"]] == ["OK"]
    failed = {f["ref"]: f for f in body["failed"]}
    assert failed[""]["where"] == "row 9" and failed[""]["errors"] == ["claim_ref is blank"]
    assert failed["NOPAT"]["errors"] == ["Patient PAT999999 is not registered"]
    assert failed["BADCPT"]["errors"] == ["Line 1: unknown CPT code 00000"]
    assert failed["MIXED"]["where"] == "rows 5, 6"
    assert "different payer_id" in failed["MIXED"]["errors"][0]
    assert "Every diagnosis needs a service line: add one for I10" in failed["NODX"]["errors"][0]
    assert "service_date isn't a date" in failed["BADDATE"]["errors"][0]


def test_an_excel_file_reads_like_a_csv(client, today):
    rows = [
        {"claim_ref": "X1", "patient_id": "PAT000003", "payer_id": "PAY001", "provider_id": "PROV001",
         "service_date": pd.Timestamp("2026-01-05"), "diagnoses": "E11.65", "cpt_code": 99213,
         "member_id": "MBR123456"},
    ]
    out = io.BytesIO()
    pd.DataFrame(rows).to_excel(out, index=False)
    res = upload(client, out.getvalue(), filename="claims.xlsx")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["file_type"] == "xlsx" and body["failed"] == []
    assert body["created"][0]["claim"]["service_date"] == "2026-01-05"


def test_files_that_arent_claims_are_refused(client):
    assert "missing the columns" in upload(client, "name,amount\nx,1\n").json()["detail"]
    assert upload(client, b"\x89PNG....", filename="scan.png").status_code == 422
    res = client.post("/api/claims/import", json={"filename": "a.csv", "content": "not base64!"})
    assert res.status_code == 422
    assert "No claims" in upload(client, "ISA" + "*" * 102 + ":~GS*HC~ST*837~SE~", filename="x.837").json()["detail"]


def test_only_roles_that_enter_claims_can_upload(anon_client):
    analyst = sign_in(anon_client, Role.ANALYST)
    assert upload(analyst, csv_file()).status_code == 403
    assert analyst.get("/api/claims/import/template.csv").status_code == 403


def test_an_upload_is_audited_with_its_claims(client, today):
    res = upload(client, csv_file("A,PAT000003,PAY001,PROV001,2026-01-05,E11.65,99213,,1,MBR1"))
    claim_id = res.json()["created"][0]["claim"]["claim_id"]
    [event] = [e for e in get_audit_log("meridian").events() if e.action == "POST /api/claims/import"]
    assert event.detail["claim_ids"] == [claim_id]
    assert event.detail["patient_ids"] == ["PAT000003"]
    assert (event.detail["import_file_type"], event.detail["failed"]) == ("csv", 0)


# ----- 837 ----------------------------------------------------------------------


def test_a_submitted_837p_reads_back_into_the_same_claim(client, today):
    original, download = submitted_837(
        client,
        diagnoses=["E11.65", "I10"],
        lines=[
            {"cpt_code": "99213", "icd10_pointer": "E11.65", "modifier": "25"},
            {"cpt_code": "99214", "icd10_pointer": "I10", "units": 2, "charge_amount": 310},
        ],
        pa_required=True,
        pa_obtained=True,
        pa_number="PA-777",
    )
    res = upload(client, download.text, filename="claim.837")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["file_type"] == "837P" and body["failed"] == []
    [created] = body["created"]
    assert created["ref"] == original["claim_id"]
    copy = client.get(f"/api/claims/{created['claim']['claim_id']}").json()
    same = ("patient_id", "payer_id", "provider_id", "facility_id", "service_date", "primary_icd10",
            "additional_icd10", "claim_type", "place_of_service", "pa_number", "total_charge")
    assert {f: copy[f] for f in same} == {f: original[f] for f in same}
    assert copy["status"] == "Draft" and copy["claim_id"] != original["claim_id"]
    assert [(l["cpt_code"], l["modifier"], l["units"], l["charge_amount"], l["icd10_pointer"]) for l in copy["lines"]] == [
        ("99213", "25", 1, 95.0, "E11.65"),
        ("99214", None, 2, 310.0, "I10"),
    ]
    assert copy["billing"]["policy"]["member_id"] == NEW_CLAIM["billing"]["policy"]["member_id"]
    assert copy["billing"]["patient_birth_date"] == NEW_CLAIM["billing"]["patient_birth_date"]


def test_an_837i_reads_back_with_its_ub04_codes(client, today):
    billing = {
        **NEW_CLAIM["billing"],
        "institutional": {"type_of_bill": "131", "admission_type": "3", "admission_source": "1", "patient_status": "01"},
    }
    lines = [{"cpt_code": "99213", "icd10_pointer": "E11.65", "revenue_code": "0510"}]
    original, download = submitted_837(client, claim_type="Institutional", billing=billing, lines=lines)
    [created] = upload(client, download.text, filename="claim.txt").json()["created"]
    copy = client.get(f"/api/claims/{created['claim']['claim_id']}").json()
    assert copy["claim_type"] == "Institutional"
    assert copy["billing"]["institutional"] == billing["institutional"]
    assert [line["revenue_code"] for line in copy["lines"]] == ["0510"]
    assert any("place of service" in note for note in created["notes"])


def test_a_dependent_and_other_coverage_read_back(client, today):
    billing = {
        **NEW_CLAIM["billing"],
        "policy": {
            "member_id": "BCX987", "group_number": "G-55", "relationship": "spouse",
            "first_name": "Maria", "last_name": "Davis", "birth_date": "1974-02-11", "sex": "F",
        },
        "other_policies": [{"member_id": "MCR555"}],
    }
    original, download = submitted_837(client, payer_id="PAY002", other_payer_ids=["PAY001"], billing=billing)
    [created] = upload(client, download.text, filename="claim.837").json()["created"]
    copy = client.get(f"/api/claims/{created['claim']['claim_id']}").json()
    assert (copy["patient_id"], copy["payer_id"], copy["other_payer_ids"]) == ("PAT000003", "PAY002", ["PAY001"])
    assert copy["billing"]["policy"] == {**billing["policy"]}
    assert copy["billing"]["other_policies"][0]["member_id"] == "MCR555"


def test_an_837_with_several_claims_and_one_unknown_patient(client, today):
    _, first = submitted_837(client)
    _, second = submitted_837(client, service_date="2026-01-07", submission_date="2026-01-08")

    def body(text):  # the claim's loops, without the envelope
        segs = segments(text)
        start = next(i for i, s in enumerate(segs) if s.startswith("HL*1*"))
        end = next(i for i, s in enumerate(segs) if s.startswith("SE*"))
        return segs[start:end]

    segs = segments(first.text)
    head = segs[: next(i for i, s in enumerate(segs) if s.startswith("HL*1*"))]
    stranger = [s.replace("NM1*IL*1*DAVIS*DONALD", "NM1*IL*1*NOBODY*ANNA") for s in body(second.text)]
    combined = "~".join([*head, *body(first.text), *body(second.text), *stranger, "SE*1*0001", "GE*1*1", "IEA*1*1"]) + "~"
    res = upload(client, combined, filename="batch.837").json()
    assert res["claims_found"] == 3
    assert [c["claim"]["service_date"] for c in res["created"]] == ["2026-01-05", "2026-01-07"]
    [failure] = res["failed"]
    assert failure["where"] == "claim 3 in the file"
    assert failure["errors"] == ["No registered patient is named ANNA NOBODY"]


def test_a_blank_facility_is_the_organisations_only_one(anon_client, today):
    # Lakeside has one facility (FAC901), not Meridian's FAC001
    lakeside = sign_in(anon_client, Role.BILLER, org="lakeside")
    res = upload(lakeside, csv_file("L1,PAT900001,PAY002,PROV901,2026-01-05,E11.65,99213,,1,"))
    assert res.status_code == 200, res.text
    [created] = res.json()["created"]
    assert created["claim"]["facility_id"] == "FAC901"
