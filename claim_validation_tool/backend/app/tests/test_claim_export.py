"""Taking a handed-off claim back to the billing system: the 837 with its corrections, and the
list of what changed."""

from datetime import UTC, datetime, timedelta

from app.data import repository
from app.data.audit import get_audit_log
from app.data.claim_changes import get_claim_change_log
from app.data.corrections import get_correction_store
from app.data.new_claims import get_new_claim_store
from app.models import AuditQuery, ClaimChange, ClaimChangeSource, Role
from app.services.claim_changes import net_changes
from app.services.edi837 import billing_system_claim_number
from app.tests.conftest import sign_in
from app.tests.test_claim_edit import edit
from app.tests.test_claim_entry import NEW_CLAIM, create, submit
from app.tests.test_claim_import import upload
from app.tests.test_claim_routes import hand_off, reopen


def handed_off(client, **changes) -> str:
    claim_id = create(client, **changes).json()["claim"]["claim_id"]
    assert hand_off(client, claim_id, acknowledge_open_issues=True).status_code == 200
    return claim_id


def export(client, claim_id):
    return client.get(f"/api/claims/{claim_id}/handoff")


def apply_prior_auth_fix(client, claim_id, number="PA123"):
    """Fix the open prior auth error (RULE-002) through AI Fix."""
    fixes = client.get(f"/api/aifix/{claim_id}").json()
    suggestion = next(s for s in fixes["suggestions"] if "RULE-002" in s["id"])
    return client.post(
        f"/api/aifix/{claim_id}/apply",
        json={"suggestion_id": suggestion["id"], "values": {"pa_number": number}},
    )


def test_the_837_is_only_available_once_handed_off(client, today):
    claim_id = create(client).json()["claim"]["claim_id"]
    for path in ("handoff", "handoff/837", "handoff/changes.pdf"):
        assert client.get(f"/api/claims/{claim_id}/{path}").status_code == 409
    submit(client, claim_id)
    assert client.get(f"/api/claims/{claim_id}/handoff/837").status_code == 409


def test_the_837_carries_the_corrections_and_is_a_first_time_claim(client, today):
    claim_id = create(client, pa_required=True).json()["claim"]["claim_id"]
    assert apply_prior_auth_fix(client, claim_id).status_code == 200
    hand_off(client, claim_id, acknowledge_open_issues=True)

    res = client.get(f"/api/claims/{claim_id}/handoff/837")
    assert res.status_code == 200, res.text
    assert f"{claim_id}_837P_handoff_TEST.txt" in res.headers["content-disposition"]
    assert "REF*G1*PA123~" in res.text
    assert ":B:1*" in res.text  # frequency 1: nothing has reached a payer
    # It stays an exported file, not a submission
    claim = client.get(f"/api/claims/{claim_id}").json()
    assert claim["status"] == "Handed off" and claim["edi"] is None


def test_every_download_of_a_claim_has_the_same_control_number(client, today):
    claim_id = handed_off(client)
    number = lambda text: text.split("*")[13]  # noqa: E731
    first = client.get(f"/api/claims/{claim_id}/handoff/837").text
    assert number(client.get(f"/api/claims/{claim_id}/handoff/837").text) == number(first)
    # Survives a restart; a reopened and re-handed-off claim is a new file
    repository.get_repository.cache_clear()
    get_new_claim_store.cache_clear()
    assert number(client.get(f"/api/claims/{claim_id}/handoff/837").text) == number(first)
    reopen(client, claim_id)
    hand_off(client, claim_id)
    assert number(client.get(f"/api/claims/{claim_id}/handoff/837").text) != number(first)


def test_reading_the_summary_takes_no_control_number(client, today):
    claim_id = handed_off(client)
    summary = export(client, claim_id).json()
    assert summary["edi"]["transaction"] == "837P" and summary["edi"]["test"] is True
    assert client.get(f"/api/claims/{claim_id}").json()["handoff"]["control_number"] is None


def test_the_list_shows_an_ai_fix_with_who_made_it(client, today):
    claim_id = create(client, pa_required=True).json()["claim"]["claim_id"]
    apply_prior_auth_fix(client, claim_id)
    hand_off(client, claim_id)
    changes = {c["field"]: c for c in export(client, claim_id).json()["changes"]}
    assert changes["pa_number"]["old_value"] is None
    assert changes["pa_number"]["new_value"] == "PA123"
    assert changes["pa_number"]["source"] == "AI Fix"
    assert changes["pa_number"]["changed_by"]
    assert changes["pa_obtained"]["new_value"] == "Yes"
    assert "is_clean_claim" not in changes  # our flag; nothing to change in a billing system


def test_an_undone_fix_is_not_listed(client, today):
    claim_id = create(client, pa_required=True).json()["claim"]["claim_id"]
    apply_prior_auth_fix(client, claim_id)
    client.delete(f"/api/aifix/{claim_id}/corrections")
    hand_off(client, claim_id, acknowledge_open_issues=True)
    assert export(client, claim_id).json()["changes"] == []


def test_the_list_shows_edits_in_words_and_keeps_fixes_the_edit_folded_in(client, today):
    claim_id = create(client, pa_required=True).json()["claim"]["claim_id"]
    apply_prior_auth_fix(client, claim_id)
    billing = {**NEW_CLAIM["billing"], "policy": {"member_id": "NEW-MEMBER"}}
    res = edit(
        client, claim_id, pa_required=True, pa_obtained=True, pa_number="PA123", billing=billing,
        lines=[{**NEW_CLAIM["lines"][0], "units": 2}],
    )
    assert res.status_code == 200, res.text
    assert get_correction_store("meridian").for_claim(claim_id) == []
    hand_off(client, claim_id)

    changes = {c["field"]: c for c in export(client, claim_id).json()["changes"]}
    assert changes["pa_number"]["new_value"] == "PA123"
    assert changes["pa_number"]["source"] == "AI Fix"
    assert changes["billing.policy.member_id"]["new_value"] == "NEW-MEMBER"
    assert changes["billing.policy.member_id"]["label"] == "Policy member ID"
    assert changes["billing.policy.member_id"]["source"] == "Edited"
    assert changes["line.1.units"]["label"] == "Line 1 units"
    assert (changes["line.1.units"]["old_value"], changes["line.1.units"]["new_value"]) == ("1", "2")


def test_changes_survive_a_restart(client, today):
    claim_id = create(client).json()["claim"]["claim_id"]
    edit(client, claim_id, lines=[{**NEW_CLAIM["lines"][0], "units": 3}])
    hand_off(client, claim_id)
    get_claim_change_log.cache_clear()
    assert [c["field"] for c in export(client, claim_id).json()["changes"] if c["field"] == "line.1.units"]


def _change(new, old=None, minutes=0):
    return ClaimChange(
        field="pa_number", label="Prior auth number", old_value=old, new_value=new,
        source=ClaimChangeSource.EDIT, changed_by="ana",
        changed_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minutes),
    )


def test_a_value_changed_twice_shows_once_and_one_changed_back_not_at_all():
    twice = net_changes([_change("B", "A", 1), _change("C", "B", 2)])
    assert [(c.old_value, c.new_value) for c in twice] == [("A", "C")]
    assert net_changes([_change("B", "A", 1), _change("A", "B", 2)]) == []


def test_the_changes_pdf_is_downloadable_and_audited(client, today):
    claim_id = handed_off(client, pa_required=True)
    res = client.get(f"/api/claims/{claim_id}/handoff/changes.pdf")
    assert res.status_code == 200
    assert res.content.startswith(b"%PDF")
    assert f"{claim_id}_changes.pdf" in res.headers["content-disposition"]


def test_downloads_are_audited_without_values(client, today):
    claim_id = create(client).json()["claim"]["claim_id"]
    billing = {**NEW_CLAIM["billing"], "policy": {"member_id": "SECRET-MEMBER"}}
    edit(client, claim_id, billing=billing)
    hand_off(client, claim_id)
    client.get(f"/api/claims/{claim_id}/handoff/837")
    client.get(f"/api/claims/{claim_id}/handoff/changes.pdf")
    events = get_audit_log("meridian").search(AuditQuery(record_id=claim_id))
    by_action = {e.action: e.detail for e in events}
    assert by_action["GET /api/claims/{claim_id}/handoff/837"]["export"] == "837P hand-off"
    assert "billing.policy.member_id" in by_action["GET /api/claims/{claim_id}/handoff/changes.pdf"]["changes"]
    assert "SECRET-MEMBER" not in str([e.detail for e in events])


def test_only_roles_that_change_claims_can_export(client, today):
    claim_id = handed_off(client)
    sign_in(client, Role.ANALYST)
    for path in ("handoff", "handoff/837", "handoff/changes.pdf"):
        assert client.get(f"/api/claims/{claim_id}/{path}").status_code == 403


def test_self_pay_has_a_changes_list_but_no_837(client, today):
    billing = {k: v for k, v in NEW_CLAIM["billing"].items() if k != "policy"}
    self_pay = next(p for p in client.get("/api/payers").json() if p["payer_type"] == "Self-Pay")
    claim_id = handed_off(client, payer_id=self_pay["payer_id"], billing=billing)
    assert export(client, claim_id).json()["edi"] is None
    assert client.get(f"/api/claims/{claim_id}/handoff/837").status_code == 404
    assert client.get(f"/api/claims/{claim_id}/handoff/changes.pdf").status_code == 200


def test_an_uploaded_claim_goes_back_under_the_hospitals_own_number(client, today):
    header = "claim_ref,patient_id,payer_id,provider_id,service_date,diagnoses,cpt_code,icd10_pointer,units\n"
    first = NEW_CLAIM
    line = first["lines"][0]
    row = (
        f"HOSP-77,{first['patient_id']},{first['payer_id']},{first['provider_id']},"
        f"{first['service_date']},{first['diagnoses'][0]},{line['cpt_code']},{line['icd10_pointer']},1\n"
    )
    res = upload(client, header + row)
    assert res.status_code == 200, res.text
    assert res.json()["created"], res.text
    claim_id = res.json()["created"][0]["claim"]["claim_id"]
    assert client.get(f"/api/claims/{claim_id}").json()["source_ref"] == "HOSP-77"

    # An edit doesn't lose it, and a restart doesn't either
    edit(client, claim_id, lines=[{**line, "units": 2}])
    repository.get_repository.cache_clear()
    hand_off(client, claim_id, acknowledge_open_issues=True)
    assert export(client, claim_id).json()["source_ref"] == "HOSP-77"
    text = client.get(f"/api/claims/{claim_id}/handoff/837").text
    assert "CLM*HOSP-77*" in text


def test_a_number_an_837_cant_carry_falls_back_to_our_id():
    assert billing_system_claim_number("abc-1") == "ABC-1"
    assert billing_system_claim_number("X" * 39) is None
    assert billing_system_claim_number(None) is None
