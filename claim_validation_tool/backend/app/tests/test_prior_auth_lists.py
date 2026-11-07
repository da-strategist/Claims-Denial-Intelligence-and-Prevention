"""Prior authorization lists: which services a payer requires it for, so a claim that needs one
and doesn't say so is still flagged. And what a clean claim doesn't cover."""


from app.data.audit import get_audit_log
from app.data.org_lifecycle import export_organisation
from app.data.prior_auth_lists import get_prior_auth_lists
from app.models import Role
from app.tests.conftest import sign_in
from app.tests.test_claim_api import auth, new_key, send
from app.tests.test_claim_entry import NEW_CLAIM, create
from app.tests.test_claim_import import csv_file, upload
from app.tests.test_edi import submitted_837

LISTS = "/api/organisation/prior-auth-lists"
MISSING_RULE = "Missing Prior Authorization"


def put_list(client, payer="PAY001", codes=("99213",)):
    return client.put(f"{LISTS}/{payer}", json={"cpt_codes": list(codes)})


def rules_hit(client, claim_id):
    return {f["rule_name"] for f in client.get(f"/api/validate/{claim_id}").json()["findings"]}


# ----- Which claims get flagged ----------------------------------------------------------


def test_a_listed_service_without_authorization_is_flagged(client, today):
    assert put_list(client).status_code == 200
    created = create(client).json()
    assert created["claim"]["pa_required"] is True
    assert MISSING_RULE in {f["rule_name"] for f in created["validation"]["findings"]}


def test_a_listed_service_with_authorization_passes(client, today):
    put_list(client)
    created = create(client, pa_required=True, pa_obtained=True, pa_number="AUTH-1").json()
    assert MISSING_RULE not in {f["rule_name"] for f in created["validation"]["findings"]}
    detail = client.get(f"/api/claims/{created['claim']['claim_id']}").json()
    assert detail["prior_auth_check"] == "obtained"


def test_a_service_not_on_the_list_isnt_flagged(client, today):
    put_list(client, codes=("70553",))
    created = create(client).json()
    assert created["claim"]["pa_required"] is False
    detail = client.get(f"/api/claims/{created['claim']['claim_id']}").json()
    assert detail["prior_auth_check"] == "not_needed"


def test_another_payers_list_doesnt_apply(client, today):
    put_list(client, payer="PAY002")
    created = create(client).json()
    assert created["claim"]["pa_required"] is False
    detail = client.get(f"/api/claims/{created['claim']['claim_id']}").json()
    assert detail["prior_auth_check"] == "not_assessed"


def test_marking_it_required_still_counts_without_a_list(client, today):
    created = create(client, pa_required=True).json()
    assert MISSING_RULE in {f["rule_name"] for f in created["validation"]["findings"]}


def test_an_edit_cant_untick_what_the_list_requires(client, today):
    put_list(client)
    claim_id = create(client).json()["claim"]["claim_id"]
    edited = client.put(f"/api/claims/{claim_id}", json={**NEW_CLAIM, "pa_required": False})
    assert edited.status_code == 200, edited.text
    assert edited.json()["claim"]["pa_required"] is True


def test_any_line_on_the_list_is_enough(client, today):
    put_list(client)
    lines = [
        {"cpt_code": "99214", "icd10_pointer": "E11.65"},
        {"cpt_code": "99213", "icd10_pointer": "E11.65"},
    ]
    assert create(client, lines=lines).json()["claim"]["pa_required"] is True


def test_an_837_without_a_number_is_flagged_once_the_payer_has_a_list(client, today):
    _, download = submitted_837(client)
    without_list = upload(client, download.text, "claim.837").json()
    assert without_list["created"][0]["claim"]["pa_required"] is False

    put_list(client)
    with_list = upload(client, download.text, "claim.837").json()
    [saved] = with_list["created"]
    assert saved["claim"]["pa_required"] is True and saved["claim"]["pa_obtained"] is False
    assert MISSING_RULE in {f["rule_name"] for f in saved["validation"]["findings"]}


def test_a_csv_claim_is_checked_against_the_list(client, today):
    put_list(client)
    row = "A-1,PAT000003,PAY001,PROV001,2026-01-05,E11.65,99213,E11.65,1,MBR123456"
    [saved] = upload(client, csv_file(row)).json()["created"]
    assert saved["claim"]["pa_required"] is True


def test_the_api_flags_it_and_says_what_wasnt_checked(anon_client, today):
    headers = auth(new_key()[1])
    before = send(anon_client, headers, number="BEFORE").json()
    assert before["coverage_check"] == "not_checked"
    assert before["prior_auth_check"] == "not_assessed"
    assert before["clean"] is True  # a clean claim still says what it doesn't cover

    get_prior_auth_lists("meridian").put("PAY001", ["99213"], "admin1")
    # Saved before the list: not assessed, until it's sent again
    assert anon_client.get(f"/api/v1/claims/{before['claim_id']}", headers=headers).json()["prior_auth_check"] == "not_assessed"
    again = send(anon_client, headers, number="BEFORE").json()
    assert again["action"] == "replaced"
    assert again["prior_auth_check"] == "missing"
    assert again["clean"] is False


def test_changing_a_list_leaves_saved_claims_alone(client, today):
    put_list(client)
    claim_id = create(client).json()["claim"]["claim_id"]
    assert client.delete(f"{LISTS}/PAY001").status_code == 204
    detail = client.get(f"/api/claims/{claim_id}").json()
    assert detail["pa_required"] is True and detail["prior_auth_check"] == "missing"


def test_self_pay_has_nothing_to_check(client, today):
    billing = {k: v for k, v in NEW_CLAIM["billing"].items() if k != "policy"}
    created = create(client, payer_id="PAY010", billing=billing)
    assert created.status_code == 201, created.text
    detail = client.get(f"/api/claims/{created.json()['claim']['claim_id']}").json()
    assert detail["coverage_check"] == "not_applicable"
    assert detail["prior_auth_check"] == "not_applicable"


# ----- Keeping the lists -----------------------------------------------------------------


def test_codes_are_tidied_and_the_list_replaced(client, today):
    saved = put_list(client, codes=(" 99213 ", "j1745", "99213")).json()
    assert saved["cpt_codes"] == ["99213", "J1745"] and saved["updated_by"]
    put_list(client, codes=("70553",))
    [only] = client.get(LISTS).json()
    assert only["cpt_codes"] == ["70553"]


def test_bad_lists_are_refused(client, today):
    assert put_list(client, codes=()).status_code == 422
    assert put_list(client, codes=("not a code",)).status_code == 422
    assert put_list(client, payer="PAY999").status_code == 422
    assert put_list(client, payer="PAY010").status_code == 422  # self-pay
    assert client.delete(f"{LISTS}/PAY001").status_code == 404


def test_lists_survive_a_restart_and_stay_in_the_organisation(client, today):
    put_list(client)
    get_prior_auth_lists.cache_clear()
    assert client.get(LISTS).json()[0]["payer_id"] == "PAY001"
    assert get_prior_auth_lists("lakeside").all() == []


def test_only_administrators_change_lists_but_staff_can_read_them(client, today):
    biller = sign_in(client, Role.BILLER)
    assert biller.get(LISTS).status_code == 200
    assert put_list(biller).status_code == 403
    assert biller.delete(f"{LISTS}/PAY001").status_code == 403


def test_a_key_cant_reach_the_lists(anon_client, today):
    assert anon_client.get(LISTS, headers=auth(new_key()[1])).status_code == 401


def test_changes_are_audited_and_included_in_the_export(client, today):
    put_list(client, codes=("99213", "70553"))
    event = [e for e in get_audit_log("meridian").events() if e.action == f"PUT {LISTS}/{{payer_id}}"][-1]
    assert event.detail["codes"] == 2
    _, manifest = export_organisation("meridian", "admin1")
    assert any("prior_auth_lists.json" in str(f) for f in manifest["files"])
