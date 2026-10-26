"""Chat suggestions: starter questions, follow-ups, grounded next steps."""

from pathlib import Path

import pytest

from backend.app.models.policy import DocumentChunk
from backend.app.services import suggestions
from backend.app.services.document_processor import chunk_text, extract_text_from_pdf
from backend.app.services.rag import _about_subject, _scored_paragraphs
from backend.app.services.retrieval import retrieve

POLICY_DIR = Path(__file__).resolve().parents[3] / "data" / "policies"
PREFIXES = {
    "apex": "apex_health_gold_ppo_2025.pdf", "summit": "summit_care_silver_hmo_2026.pdf",
    "riverbend": "riverbend_community_care_medicaid_2025.pdf", "northwind": "northwind_bronze_hdhp_2026.pdf",
}
PRIOR_AUTH, EXCLUDED, LIMIT, REFERRAL = "prior authorization", "exclusions", "Keep track", "referral"


@pytest.fixture(scope="module")
def chunks():
    out = {}
    for key, name in PREFIXES.items():
        if not (POLICY_DIR / name).exists():
            pytest.skip(f"{name} missing")
        out[key] = chunk_text(extract_text_from_pdf(POLICY_DIR / name), key)
    return out


def _steps(question, policy_chunks):
    hits = retrieve(question, policy_chunks, 5)
    quoted = [(cid, t) for _, cid, t in _scored_paragraphs(question, hits)[:4]]
    return [s["text"] for s in suggestions.next_steps(_about_subject(question, quoted), hits)]


def _kinds(steps):
    kinds = set()
    for s in steps:
        if PRIOR_AUTH in s:
            kinds.add("prior_auth")
        if EXCLUDED in s:
            kinds.add("excluded")
        if s.startswith(LIMIT):
            kinds.add("limit")
        if REFERRAL in s:
            kinds.add("referral")
    return kinds


# Expected next-step kinds, checked against each policy's text.
CASES = [
    ("apex", "Is an MRI covered?", {"prior_auth"}),
    ("apex", "Is cosmetic surgery covered?", {"excluded"}),                    # not "prior auth" from outpatient surgery
    ("apex", "How many physical therapy visits do I get?", {"limit", "prior_auth"}),  # PA after 12 visits
    ("apex", "Do I need a referral to see a specialist?", set()),             # "does not require referrals"
    ("summit", "Do I need a referral to see a specialist?", {"referral"}),
    ("summit", "How many physical therapy visits do I get?", {"limit"}),      # "up to 20 combined visits"
    ("summit", "Is genetic testing covered?", set()),                         # not in this policy
    ("riverbend", "Is an MRI covered?", {"prior_auth"}),                      # bullet under an approval heading
    ("riverbend", "Do I need a referral to see a specialist?", {"referral"}),
    ("northwind", "Is an MRI covered?", {"prior_auth"}),                      # not the rehab visit limit merged in by wrapping
    ("northwind", "Do I need a referral to see a specialist?", set()),        # "No referrals are needed"
    ("northwind", "Is cosmetic surgery covered?", {"excluded"}),
]


@pytest.mark.parametrize("policy,question,expected", CASES, ids=[f"{p}:{q}" for p, q, _ in CASES])
def test_next_steps_match_the_policy_text(chunks, policy, question, expected):
    assert _kinds(_steps(question, chunks[policy])) == expected


def test_next_steps_record_where_they_came_from(chunks):
    hits = retrieve("Is an MRI covered?", chunks["apex"], 5)
    quoted = [(cid, t) for _, cid, t in _scored_paragraphs("Is an MRI covered?", hits)[:4]]
    [step] = suggestions.next_steps(_about_subject("Is an MRI covered?", quoted), hits)
    assert step["document_id"] == "apex" and step["page_number"] and step["section"]


def test_next_steps_never_promise_coverage(chunks):
    texts = [s for p in chunks.values() for q in ("Is an MRI covered?", "Is cosmetic surgery covered?")
             for s in _steps(q, p)]
    assert texts and not any("will be covered" in t.lower() or "guarantee" in t.lower() for t in texts)


def test_follow_ups_follow_the_cited_sections():
    pa = DocumentChunk(chunk_id="a", document_id="d", section_heading="PRIOR AUTHORIZATION", content="x")
    ex = DocumentChunk(chunk_id="b", document_id="d", section_heading="EXCLUSIONS", content="x")
    assert suggestions.follow_ups("Is an MRI covered?", [(pa, 1), (ex, 1)])[:2] == [
        "What does my provider need to submit for prior authorization?",
        "Are there similar services my plan does cover?",
    ]
    # don't suggest the question's own topic, and never two prior-auth follow-ups
    ups = suggestions.follow_ups("What needs prior authorization?", [(pa, 1)])
    assert sum("prior authorization" in u for u in ups) <= 1 and len(ups) == 3


def test_starters_use_plan_names_services_and_dates():
    entries = [{"document_id": "d1", "filename": "a.pdf", "plan_name": "Gold PPO",
                "expiration_date": "2025-12-31"},
               {"document_id": "d2", "filename": "b.pdf", "display_name": "Work plan"}]
    qs = suggestions.starters(entries, {"d1": ["PREVENTIVE CARE"]})
    assert qs[0] == "Which of my plans has the lower deductible?"
    assert "Is preventive care covered under Gold PPO?" in qs
    assert "When does Gold PPO start and end?" in qs
    assert any("Work plan" in q for q in qs)
    assert len(qs) <= suggestions.MAX_STARTERS and len(set(qs)) == len(qs)
    assert suggestions.starters([], {})  # generic starters with no documents


# ── Starter questions are answered from the right section ────────────

APPROVAL_SECTION = {"apex": "PRIOR AUTHORIZATION", "summit": "Advance Approval",
                    "northwind": "PRECERTIFICATION", "riverbend": "approval first"}


@pytest.mark.parametrize("policy", APPROVAL_SECTION)
def test_prior_auth_question_finds_the_approval_section_whatever_its_name(chunks, policy):
    """Each policy names the process differently (prior authorization,
    advance approval, precertification, approval first)."""
    from backend.app.services.retrieval import adapt_vocabulary

    query = adapt_vocabulary("What needs prior authorization?", chunks[policy])
    [(top, _)] = retrieve(query, chunks[policy], 1)
    assert APPROVAL_SECTION[policy].lower() in top.section_heading.lower()


def test_wording_is_kept_when_the_policy_uses_it(chunks):
    from backend.app.services.retrieval import adapt_vocabulary

    assert adapt_vocabulary("Does an MRI need prior auth?", chunks["northwind"]) == "does an mri need precertification?"
    assert adapt_vocabulary("What needs prior authorization?", chunks["apex"]) == "What needs prior authorization?"
    assert adapt_vocabulary("What is my deductible?", chunks["northwind"]) == "What is my deductible?"
