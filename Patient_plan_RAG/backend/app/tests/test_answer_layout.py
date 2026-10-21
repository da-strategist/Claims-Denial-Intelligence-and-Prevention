"""Chat answer layout: what the policy says (grouped by plan), differences
between plans, and the fixed keep-in-mind note."""

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.auth.users import Role
from backend.app.services import answer_layout, records, suggestions
from backend.app.tests.conftest import POLICY_PDF, sign_in

NORTHWIND = POLICY_PDF.parent / "northwind_bronze_hdhp_2026.pdf"


def _upload(client, path, **form):
    with path.open("rb") as f:
        r = client.post("/api/policies/upload", data=form, files={"file": (path.name, f, "application/pdf")})
    assert r.status_code == 200, r.text
    return r.json()["document_id"]


@pytest.fixture
def alice(data_dirs):
    if not NORTHWIND.exists():
        pytest.skip("northwind policy missing")
    c = sign_in(TestClient(main.app), "alice@example.com")
    return c, _upload(c, POLICY_PDF), _upload(c, NORTHWIND)


def test_two_plans_are_shown_separately_with_differences(alice):
    client, apex, northwind = alice
    r = client.post("/api/chat", json={"question": "What is my deductible?"}).json()
    assert {q["document_id"] for q in r["policy_says"]} == {apex, northwind}
    assert len(r["policy_says"]) == 2  # the best passage of each plan
    assert "matches 2 of your plans" in r["lead"]
    [diff] = [d for d in r["differences"] if d["topic"] == "Deductible"]
    values = {v["document_id"]: v["value"] for v in diff["values"]}
    assert "$1,500" in values[apex] and "$7,000" in values[northwind]
    assert {v["document_name"] for v in diff["values"]} == {"Gold PPO Plan", "Bronze HDHP 7000"}
    # each plan's quote is its own deductible wording, with where it comes from
    quotes = {q["document_id"]: q for q in r["policy_says"]}
    assert "$1,500" in quotes[apex]["quote"] and "DEDUCTIBLE" in quotes[apex]["section"]
    assert "$7,000" in quotes[northwind]["quote"] and quotes[northwind]["page_number"] == 1


def test_naming_a_plan_shows_only_that_plan(alice):
    client, apex, northwind = alice
    r = client.post("/api/chat", json={"question": "What is the deductible under Bronze HDHP 7000?"}).json()
    assert {q["document_id"] for q in r["policy_says"]} == {northwind}
    assert r["differences"] == [] and r["lead"].startswith("Here is what your policy says")


def test_quotes_carry_name_page_and_section(alice):
    client, apex, _ = alice
    r = client.post("/api/chat", json={"question": "Is an MRI covered?", "policy_id": apex}).json()
    q = r["policy_says"][0]
    assert q["document_name"] == "Gold PPO Plan" and q["page_number"] and q["section"]
    assert q["quote"] in r["answer"]


def test_every_answer_has_the_fixed_note(alice):
    client, apex, _ = alice
    r = client.post("/api/chat", json={"question": "Is an MRI covered?", "policy_id": apex}).json()
    assert r["keep_in_mind"] == answer_layout.KEEP_IN_MIND[suggestions.MEMBER]
    assert "not an approval" in r["keep_in_mind"] and "does not guarantee payment" in r["keep_in_mind"]
    assert r["keep_in_mind"] in r["answer"]  # also in the plain-text answer
    none = client.post("/api/chat", json={"question": "What is the capital of France?",
                                          "policy_id": apex}).json()
    assert none["policy_says"] == [] and none["keep_in_mind"]


def test_staff_get_staff_wording(data_dirs):
    org = records.orgs.add(records.Org(records.new_id(), "General Hospital"))
    staff = sign_in(TestClient(main.app), "gs@general.example", Role.HOSPITAL_STAFF, org.org_id)
    pid = staff.post("/api/hospital/patients", json={"name": "Pat"}).json()["patient_id"]
    _upload(staff, POLICY_PDF, patient_id=pid)
    r = staff.post("/api/chat", json={"question": "What is the deductible?", "patient_id": pid}).json()
    assert r["keep_in_mind"] == answer_layout.KEEP_IN_MIND[suggestions.STAFF]
    assert "the patient's policy" in r["lead"]


def test_amounts_that_match_are_not_flagged():
    assert answer_layout._amounts("$1,500 individual / $3,000 family") == {"$1500", "$3000"}
    assert answer_layout._amounts("20 %") == {"20%"}
