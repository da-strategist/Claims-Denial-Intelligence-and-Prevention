""""Is this plan still active?" is answered from the plan dates the document
states (quoted with page and section) compared with today, never from
keyword search, and always says the dates don't confirm enrolment."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.models.policy import DocumentChunk
from backend.app.services import plan_status, suggestions
from backend.app.services.document_processor import find_plan_period
from backend.app.tests.conftest import POLICY_PDF, sign_in

SUMMIT = POLICY_PDF.parent / "summit_care_silver_hmo_2026.pdf"


@pytest.mark.parametrize("text,start,end", [
    ("Effective Date: January 1, 2026\nExpiration Date: December 31, 2026", date(2026, 1, 1), date(2026, 12, 31)),
    ("Effective Date: 07/01/2025\nEnd Date: 06/30/2026", date(2025, 7, 1), date(2026, 6, 30)),
    ("Coverage Period: 01/01/2026 - 12/31/2026", date(2026, 1, 1), date(2026, 12, 31)),
    ("Plan year: March 1, 2026 through February 28, 2027", date(2026, 3, 1), date(2027, 2, 28)),
    ("Policy Year: August 15, 2025 to August 14, 2026", date(2025, 8, 15), date(2026, 8, 14)),
    ("Plan effective 2026-01-01 through 2026-12-31", date(2026, 1, 1), date(2026, 12, 31)),
    ("Benefit Period: 1 April 2026 – 31 March 2027", date(2026, 4, 1), date(2027, 3, 31)),
    ("January 1 – December 31, 2026\nEvidence of Coverage", date(2026, 1, 1), date(2026, 12, 31)),
    ("Effective Date: January 1, 2026", date(2026, 1, 1), None),
])
def test_plan_period_layouts(text, start, end):
    got_start, got_end, line = find_plan_period(text)
    assert (got_start, got_end) == (start, end)
    assert line and all(part in text for part in line.splitlines())  # verbatim


@pytest.mark.parametrize("text", [
    "Plan Year 2026 | Plan ID: X-1",                  # a year is not a period
    "Deductible: $1,500 per plan year",
    "Benefit Period: sometime next year",
    "",
])
def test_no_dates_are_guessed(text):
    assert find_plan_period(text) == (None, None, "")


@pytest.mark.parametrize("question", [
    "Is this plan still active?", "Is my policy expired?", "Is my coverage still in effect?",
    "When does my coverage end?", "When does the plan start?", "What is the effective date?",
    "What are the plan dates?", "Is it still valid?", "What is the coverage period?",
])
def test_status_questions(question):
    assert plan_status.is_status_question(question)


@pytest.mark.parametrize("question", [
    "Is an MRI covered?", "How long is a prior authorization valid?", "What is my deductible?",
    "Does the referral expire?", "Is physical therapy covered for active injuries?", "Are glasses covered?",
    "When does my prescription expire?", "How do I appeal a claim?",
])
def test_other_questions(question):
    assert not plan_status.is_status_question(question)


def _chunk(doc, text, page=1, section="PLAN INFORMATION"):
    return DocumentChunk(chunk_id=f"{doc}_0", document_id=doc, page_number=page,
                         section_heading=section, content=text, content_lower=text.lower())


@pytest.mark.parametrize("today,status", [
    (date(2026, 6, 1), "today (June 1, 2026) falls within the plan period"),
    (date(2027, 1, 2), "the plan period ended on December 31, 2026"),
    (date(2025, 12, 1), "has not started yet (it starts on January 1, 2026)"),
])
def test_status_against_today(today, status):
    chunks = [_chunk("d1", "Coverage Period: 01/01/2026 - 12/31/2026\nPlan ID: X")]
    out = plan_status.answer(chunks, {"d1": "Silver"}, suggestions.MEMBER, today=today)
    assert status in out["lead"]
    assert "don't show whether you are still enrolled" in out["lead"]
    [q] = out["quotes"]
    assert (q["quote"], q["page_number"], q["section"]) == (
        "Coverage Period: 01/01/2026 - 12/31/2026", 1, "PLAN INFORMATION")


def test_staff_wording_and_plans_without_dates():
    chunks = [_chunk("d1", "Effective Date: January 1, 2026\nExpiration Date: December 31, 2026"),
              _chunk("d2", "Deductible: $500")]
    out = plan_status.answer(chunks, {"d1": "Silver", "d2": "Bronze"}, suggestions.STAFF,
                             today=date(2026, 3, 1))
    assert "Silver: By these dates" in out["lead"] and "No plan dates were found in: Bronze" in out["lead"]
    assert "verify current eligibility with the payer" in out["lead"]
    assert plan_status.answer([_chunk("d2", "Deductible: $500")], {}, suggestions.MEMBER) is None


@pytest.fixture
def alice(data_dirs):
    if not SUMMIT.exists():
        pytest.skip("summit policy missing")
    c = sign_in(TestClient(main.app), "alice@example.com")
    ids = []
    for path in (POLICY_PDF, SUMMIT):
        with path.open("rb") as f:
            r = c.post("/api/policies/upload", files={"file": (path.name, f, "application/pdf")})
        ids.append(r.json()["document_id"])
    return c, *ids


def test_chat_answers_from_the_stated_dates(alice):
    client, apex, summit = alice
    r = client.post("/api/chat", json={"question": "Is this plan still active?", "policy_id": summit}).json()
    assert r["confidence"] == "supported"
    [q] = r["policy_says"]
    assert q["quote"] == "Effective Date: January 1, 2026\nExpiration Date: December 31, 2026"
    assert q["page_number"] == 1 and q["document_name"] == "Silver HMO Value"
    assert r["citations"][0]["excerpt"] == q["quote"]
    assert "plan period" in r["lead"] and r["keep_in_mind"] in r["answer"]
    # across both plans, each plan's own dates
    both = client.post("/api/chat", json={"question": "When does my coverage end?"}).json()
    assert {q["document_id"] for q in both["policy_says"]} == {apex, summit}
    assert "Gold PPO Plan: " in both["lead"] and "Silver HMO Value: " in both["lead"]
