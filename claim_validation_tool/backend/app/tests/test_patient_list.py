"""The patient list keeps itself up to date from claims: nobody registered with the hospital
is refused for being new, and an unclear match is flagged rather than merged."""

import json

import pytest

from app.data.audit import get_audit_log
from app.data.new_claims import get_new_claim_store
from app.data.org_lifecycle import PHI_FILES
from app.data.patient_list import get_patient_list
from app.data.registrations import get_registration_store
from app.data.repository import get_repository
from app.models import Role
from app.services.assistant import get_name_scrubber
from app.tests.conftest import org_folder, sign_in
from app.tests.test_claim_api import URL, auth, new_key, rows, send_file
from app.tests.test_claim_entry import NEW_CLAIM
from app.tests.test_claim_import import upload
from app.tests.test_edi import segments, submitted_837

BILLING = {
    "patient_birth_date": "1990-03-14",
    "patient_address": {"line1": "9 Elm St", "city": "Charlotte", "state": "NC", "zip_code": "28202"},
    "policy": {"member_id": "NEW555"},
}


@pytest.fixture
def headers(anon_client, today):
    return auth(new_key()[1])


def claim(number="N-1", first="Amara", last="Okafor", **changes):
    body = {k: v for k, v in NEW_CLAIM.items() if k != "patient_id"}
    return {
        **body,
        "claim_number": number,
        "patient": {"first_name": first, "last_name": last, "sex": "F"},
        "billing": BILLING,
        **changes,
    }


def send(client, headers, *args, **kwargs):
    return client.post(URL, json=claim(*args, **kwargs), headers=headers)


def repo():
    return get_repository("meridian")


# ----- New patients ----------------------------------------------------------------------


def test_a_new_patient_is_added_and_their_claim_validated(anon_client, headers):
    res = send(anon_client, headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["action"], body["patient_added"], body["patient_needs_review"]) == ("created", True, False)
    assert body["status"] == "Draft" and "findings" in body
    patient = repo().get_patient(body["patient_id"])
    assert (patient.first_name, patient.last_name, patient.gender, patient.primary_payer_id, patient.zip_code) == (
        "Amara", "Okafor", "F", "PAY001", "28202",
    )
    assert patient.age == 35  # on the pinned date, 2026-01-10
    assert "Okafor" not in res.text


def test_a_returning_patient_is_matched_not_added_again(anon_client, headers):
    first = send(anon_client, headers).json()
    second = send(anon_client, headers, number="N-2", first="AMARA", last="okafor").json()
    assert second["patient_id"] == first["patient_id"]
    assert (second["patient_added"], second["patient_needs_review"]) == (False, False)
    assert repo().get_patient(first["patient_id"]).claim_count == 2


def test_their_details_are_kept_up_to_date(anon_client, headers):
    first = send(anon_client, headers).json()
    moved = {**BILLING, "patient_address": {**BILLING["patient_address"], "zip_code": "28210"}, "policy": {"member_id": "NEW999"}}
    send(anon_client, headers, number="N-2", payer_id="PAY002", billing=moved)
    patient = repo().get_patient(first["patient_id"])
    assert (patient.zip_code, patient.primary_payer_id) == ("28210", "PAY002")
    registration = get_registration_store("meridian")._entered[first["patient_id"]]
    assert registration.policies["PAY002"].member_id == "NEW999"


def test_a_change_of_primary_payer_doesnt_alter_earlier_claims_after_a_restart(anon_client, headers):
    first = send(anon_client, headers).json()
    before = anon_client.get(f"{URL}/{first['claim_id']}", headers=headers).json()
    send(anon_client, headers, number="N-2", payer_id="PAY002")
    get_repository.cache_clear()
    get_patient_list.cache_clear()
    get_new_claim_store.cache_clear()
    after = anon_client.get(f"{URL}/{first['claim_id']}", headers=headers).json()
    assert after["findings"] == before["findings"]


def test_the_list_survives_a_restart_and_stays_encrypted(anon_client, headers):
    patient_id = send(anon_client, headers).json()["patient_id"]
    path = org_folder() / "patient_list.json"
    assert "patient_list.json" in PHI_FILES
    assert b"Okafor" not in path.read_bytes()
    get_repository.cache_clear()
    get_patient_list.cache_clear()
    get_new_claim_store.cache_clear()
    assert repo().get_patient(patient_id).last_name == "Okafor"
    assert send(anon_client, headers, number="N-2").json()["patient_id"] == patient_id


def test_the_source_table_is_never_touched(anon_client, headers):
    before = (repo().data_dir / "dim_patients.csv").read_bytes()
    send(anon_client, headers)
    assert (repo().data_dir / "dim_patients.csv").read_bytes() == before


def test_no_one_is_listed_when_their_claim_cant_be_saved(anon_client, headers):
    res = send(anon_client, headers, lines=[{"cpt_code": "00000", "icd10_pointer": "E11.65"}])
    assert res.status_code == 422
    from app.models import PatientQuery

    assert repo().list_patients(PatientQuery(search="Okafor")).total == 0
    assert get_patient_list("meridian").records() == {}


def test_a_failed_claim_doesnt_change_a_known_patient(anon_client, headers):
    patient_id = send(anon_client, headers).json()["patient_id"]
    res = send(anon_client, headers, number="N-2", payer_id="PAY002", lines=[{"cpt_code": "00000", "icd10_pointer": "E11.65"}])
    assert res.status_code == 422
    assert repo().get_patient(patient_id).primary_payer_id == "PAY001"


def test_the_assistant_masks_new_patients_names(anon_client, headers):
    before = get_name_scrubber("meridian").scrub("Amara Okafor was denied")
    assert "Okafor" in before
    send(anon_client, headers)
    assert "Okafor" not in get_name_scrubber("meridian").scrub("Amara Okafor was denied")


def test_patient_id_or_patient_but_not_both_or_neither(anon_client, headers):
    assert send(anon_client, headers, patient_id="PAT000003").status_code == 422
    body = claim()
    body.pop("patient")
    assert anon_client.post(URL, json=body, headers=headers).status_code == 422
    body["patient_id"] = "PAT000003"
    known = anon_client.post(URL, json=body, headers=headers)
    assert known.status_code == 200 and known.json()["patient_id"] == "PAT000003"


def test_adding_a_patient_is_audited_without_their_name(anon_client, headers):
    patient_id = send(anon_client, headers).json()["patient_id"]
    event = get_audit_log("meridian").events()[-1]
    assert event.records["patient_id"] == patient_id
    assert event.detail["patient_added"] is True
    assert "Okafor" not in json.dumps(event.model_dump(mode="json"))


def test_each_organisation_has_its_own_list(anon_client, headers):
    send(anon_client, headers)
    from app.models import PatientQuery

    assert get_repository("lakeside").list_patients(PatientQuery(search="Okafor")).total == 0


# ----- Unclear matches -------------------------------------------------------------------


def different_birth(number="N-2"):
    return {"number": number, "billing": {**BILLING, "patient_birth_date": "1985-07-01", "policy": {"member_id": "OTHER1"}}}


def test_same_name_different_birth_date_is_kept_apart_and_flagged(anon_client, headers):
    first = send(anon_client, headers).json()
    second = send(anon_client, headers, **different_birth()).json()
    assert second["patient_id"] != first["patient_id"]
    assert (second["patient_added"], second["patient_needs_review"]) == (True, True)
    assert second["status"] == "Draft"  # still validated


def test_same_member_id_different_name_is_flagged(anon_client, headers):
    first = send(anon_client, headers).json()
    other = {**BILLING, "patient_birth_date": "1985-07-01"}
    second = send(anon_client, headers, number="N-2", first="Chidi", last="Eze", billing=other).json()
    assert second["patient_needs_review"] is True
    assert get_patient_list("meridian").to_review()[second["patient_id"]] == [first["patient_id"]]


def test_same_birth_date_and_surname_is_flagged(anon_client, headers):
    send(anon_client, headers)
    other = {**BILLING, "policy": {"member_id": "OTHER2"}}
    second = send(anon_client, headers, number="N-2", first="Amarachi", billing=other).json()
    assert second["patient_needs_review"] is True


def test_someone_with_the_same_name_and_birthday_is_told_apart_by_member_id(anon_client, headers):
    first = send(anon_client, headers).json()
    twin = repo().add_patient(
        {"first_name": "Amara", "last_name": "Okafor", "age": 35, "gender": "F", "primary_payer_id": "PAY001", "zip_code": "28202"},
        "test",
        [],
    )
    other = {**BILLING, "policy": {"member_id": "TWIN1"}}
    sign_in(anon_client, Role.ADMIN)
    registrations = get_registration_store("meridian")
    from app.models import ClaimBilling, Sex

    registrations.record_claim(repo()._patient(twin), Sex.FEMALE, ClaimBilling.model_validate(other), ["PAY001"], "test")
    anon_client.cookies.clear()
    assert send(anon_client, headers, number="N-2", billing=other).json()["patient_id"] == twin
    assert send(anon_client, headers, number="N-3").json()["patient_id"] == first["patient_id"]


def test_staff_see_who_to_review_and_can_clear_them(anon_client, headers):
    first = send(anon_client, headers).json()
    second = send(anon_client, headers, **different_birth()).json()
    client = sign_in(anon_client, Role.BILLER)
    [item] = client.get("/api/patients/to-review").json()
    assert (item["patient_id"], item["birth_date"]) == (second["patient_id"], "1985-07-01")
    assert [(m["patient_id"], m["birth_date"]) for m in item["possible_matches"]] == [(first["patient_id"], "1990-03-14")]
    assert client.post(f"/api/patients/{second['patient_id']}/not-a-duplicate").status_code == 204
    assert client.get("/api/patients/to-review").json() == []
    assert client.post(f"/api/patients/{second['patient_id']}/not-a-duplicate").status_code == 404
    client.cookies.clear()
    again = anon_client.get(f"{URL}/{second['claim_id']}", headers=headers).json()
    assert again["patient_needs_review"] is False


def test_review_follows_permissions_and_stays_inside_the_organisation(anon_client, headers):
    send(anon_client, headers)
    second = send(anon_client, headers, **different_birth()).json()
    analyst = sign_in(anon_client, Role.ANALYST)
    assert analyst.get("/api/patients/to-review").status_code == 403
    other_org = sign_in(anon_client, Role.ADMIN, org="lakeside")
    assert other_org.get("/api/patients/to-review").json() == []
    assert other_org.post(f"/api/patients/{second['patient_id']}/not-a-duplicate").status_code == 404


# ----- Sending the same claim again ------------------------------------------------------


def test_correcting_a_typo_on_a_resend_updates_the_same_patient(anon_client, headers):
    first = send(anon_client, headers).json()
    again = send(anon_client, headers, last="Okafor-Ade", billing={**BILLING, "patient_birth_date": "1990-03-14"}).json()
    assert (again["action"], again["patient_id"], again["patient_added"]) == ("replaced", first["patient_id"], False)
    assert repo().get_patient(first["patient_id"]).last_name == "Okafor-Ade"


def test_correcting_a_birth_date_on_a_resend_keeps_one_patient(anon_client, headers):
    first = send(anon_client, headers).json()
    fixed = {**BILLING, "patient_birth_date": "1990-03-15"}
    again = send(anon_client, headers, billing=fixed).json()
    assert (again["action"], again["patient_id"], again["patient_needs_review"]) == ("replaced", first["patient_id"], False)
    assert len(get_patient_list("meridian").records()) == 1


def test_a_claim_number_cant_move_to_a_different_person(anon_client, headers):
    send(anon_client, headers)
    other = {**BILLING, "patient_birth_date": "1970-01-01"}
    res = send(anon_client, headers, first="Chidi", last="Eze", billing=other)
    assert res.status_code == 409
    assert "different patient" in res.json()["detail"]
    assert len(get_patient_list("meridian").records()) == 1


# ----- Files ----------------------------------------------------------------------------


HEADER = (
    "claim_ref,patient_id,patient_first_name,patient_last_name,patient_sex,patient_birth_date,address_line1,city,state,zip_code,"
    "payer_id,provider_id,service_date,diagnoses,cpt_code,icd10_pointer,units,member_id"
)
NEW_ROW = ",,Amara,Okafor,F,1990-03-14,9 Elm St,Charlotte,NC,28202,PAY001,PROV001,2026-01-05,E11.65,99213,E11.65,1,NEW555"


def table(*refs):
    return "\n".join([HEADER, *[ref + NEW_ROW for ref in refs]]) + "\n"


def test_two_claims_for_a_new_patient_in_one_file_are_one_patient(client, today):
    res = upload(client, table("A1", "A2")).json()
    assert res["failed"] == [], res
    ids = {c["claim"]["patient_id"] for c in res["created"]}
    assert len(ids) == 1
    assert "added to your patient list" in res["created"][0]["notes"][0]
    assert not any("added" in note for note in res["created"][1]["notes"])
    assert get_audit_log("meridian").events()[-1].detail["patients_added"] == sorted(ids)


def test_a_file_tells_you_what_a_new_patient_is_missing(client, today):
    row = "A1,,Amara,Okafor,F,,9 Elm St,Charlotte,NC,28202,PAY001,PROV001,2026-01-05,E11.65,99213,E11.65,1,NEW555"
    [failure] = upload(client, f"{HEADER}\n{row}\n").json()["failed"]
    assert "patient_birth_date" in failure["errors"][0]
    row = "A1,,,Okafor,F,1990-03-14,9 Elm St,Charlotte,NC,28202,PAY001,PROV001,2026-01-05,E11.65,99213,E11.65,1,NEW555"
    [failure] = upload(client, f"{HEADER}\n{row}\n").json()["failed"]
    assert "patient_first_name" in failure["errors"][0]


def test_through_the_api_a_file_adds_the_patient_too(anon_client, headers):
    body = send_file(anon_client, headers, table("A1", "A2")).json()
    assert [c["patient_added"] for c in body["checked"]] == [True, False]
    again = send_file(anon_client, headers, table("A1")).json()["checked"][0]
    assert (again["action"], again["patient_added"]) == ("replaced", False)


def test_an_837_for_a_patient_weve_never_seen_goes_through(client, today):
    text = submitted_837(client)[1].text.replace("NM1*IL*1*DAVIS*DONALD", "NM1*IL*1*OKAFOR*AMARA").replace("MBR123456", "NEW555")
    text = text.replace("DMG*D8*19760502", "DMG*D8*19900314")
    res = upload(client, text, filename="stranger.837").json()
    assert res["failed"] == [], res
    created = res["created"][0]
    assert repo().get_patient(created["claim"]["patient_id"]).last_name == "OKAFOR"
    assert created["validation"]["claim_id"] == created["claim"]["claim_id"]
    assert any("added to your patient list" in note for note in created["notes"])
    assert not any("may already be" in note for note in created["notes"])


def test_an_837_uses_the_payer_it_says_is_primary(client, today):
    text = submitted_837(client)[1].text.replace("NM1*IL*1*DAVIS*DONALD", "NM1*IL*1*OKAFOR*AMARA").replace("DMG*D8*19760502", "DMG*D8*19900314")
    patient_id = upload(client, text, filename="x.837").json()["created"][0]["claim"]["patient_id"]
    assert "SBR*P" in "".join(segments(text))
    assert repo().get_patient(patient_id).primary_payer_id == "PAY001"


def test_an_837_without_a_birth_date_for_a_new_patient_says_so(client, today):
    source = submitted_837(client)[1].text.replace("NM1*IL*1*DAVIS*DONALD", "NM1*IL*1*OKAFOR*AMARA")
    without = "~".join(s for s in source.split("~") if not s.strip().startswith("DMG"))
    [failure] = upload(client, without, filename="x.837").json()["failed"]
    assert "date of birth" in failure["errors"][0]
