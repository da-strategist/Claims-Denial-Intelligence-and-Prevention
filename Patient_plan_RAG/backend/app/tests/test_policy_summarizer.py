"""Tests for the structured policy summary builder."""

from backend.app.models.policy import DocumentChunk
from backend.app.services.policy_summarizer import (
    _group_sections,
    _paragraphs,
    summarize_policy,
)


def _chunk(section, content, page=1):
    return DocumentChunk(chunk_id=f"{section}-{content[:8]}", document_id="d",
                         page_number=page, section_heading=section, content=content)


# ── Helpers ──────────────────────────────────────────────────────────

def test_group_sections_drops_overlap_lines():
    sections = _group_sections([
        _chunk("COVERED SERVICES", "COVERED SERVICES\nA: one\nB: two"),
        _chunk("COVERED SERVICES", "B: two\nC: three", page=2),
        _chunk("EXCLUSIONS", "EXCLUSIONS\n• X"),
    ])
    assert [(s.heading, s.page, s.lines) for s in sections] == [
        ("COVERED SERVICES", 1, ["COVERED SERVICES", "A: one", "B: two", "C: three"]),
        ("EXCLUSIONS", 1, ["EXCLUSIONS", "• X"]),
    ]


def test_paragraphs_rejoin_soft_wrapped_lines():
    long_line = "PREVENTIVE CARE: Covered at 100% in-network with no deductible or copay. Includes"
    assert len(long_line) >= 75
    assert _paragraphs([long_line, "annual wellness exams.", "Short line", "Another"]) == [
        long_line + " annual wellness exams.", "Short line", "Another",
    ]


def test_paragraphs_never_merge_into_bullets_or_labels():
    long_line = "x" * 90
    assert _paragraphs([long_line, "• bullet", long_line, "LABEL: text"]) == [
        long_line, "• bullet", long_line, "LABEL: text",
    ]


# ── summarize_policy (synthetic chunks) ──────────────────────────────

def test_empty_chunks_give_empty_summary():
    s = summarize_policy("d", [])
    assert s.document_id == "d" and s.covered_services == [] and s.plan_overview == ""


def test_fields_use_heading_not_first_keyword_mention():
    # "copay" appears in the out-of-pocket section first; copayments must still
    # come from the COPAYMENTS section.
    s = summarize_policy("d", [
        _chunk("OUT-OF-POCKET MAXIMUM", "OUT-OF-POCKET MAXIMUM\nIncludes deductible and copayments."),
        _chunk("COPAYMENTS", "COPAYMENTS\nSpecialist Office Visit: $50 copay", page=2),
    ])
    assert s.copayments == [{"service": "Specialist Office Visit", "amount": "$50 copay"}]
    assert s.out_of_pocket_max == {"description": "Includes deductible and copayments."}


def test_exclusion_parentheticals_become_descriptions():
    s = summarize_policy("d", [_chunk("EXCLUSIONS AND LIMITATIONS",
        "EXCLUSIONS AND LIMITATIONS\n• Dental services (covered under separate dental plan)\n• Private duty nursing")])
    assert s.excluded_services == [
        {"service": "Dental services", "description": "covered under separate dental plan"},
        {"service": "Private duty nursing", "description": "Not covered"},
    ]


def test_falls_back_to_content_when_no_heading_matches():
    s = summarize_policy("d", [_chunk("GENERAL", "GENERAL\nThe annual deductible is $500.")])
    assert s.deductible["description"] == "The annual deductible is $500."


def test_missing_sections_leave_fields_empty():
    s = summarize_policy("d", [_chunk("COPAYMENTS", "COPAYMENTS\nPrimary Care: $20")])
    assert s.excluded_services == [] and s.prior_auth_services == []
    assert s.deductible == {} and s.referral_requirements == ""


# ── summarize_policy (synthetic policy) ──────────────────────────────

def test_policy_summary_is_itemised(policy_chunks):
    s = summarize_policy("testdoc", policy_chunks)
    covered = {c["service"] for c in s.covered_services}
    assert {"PREVENTIVE CARE", "DIAGNOSTIC IMAGING", "HOSPICE CARE"} <= covered
    assert len(s.excluded_services) == 12
    assert len(s.prior_auth_services) == 14
    assert {"service": "Specialist Office Visit", "amount": "$50 copay (no deductible)"} in s.copayments
    assert s.coinsurance["description"].startswith("In-Network: Plan pays 80%")
    assert any("limited to 30 visits" in lim for lim in s.important_limitations)


def test_policy_summary_text_is_verbatim(policy_pages, policy_chunks):
    """Every itemised value must appear in the source text (no fabrication)."""
    source = " ".join(
        line.replace("(cid:127)", "•").strip()
        for p in policy_pages for line in p["text"].split("\n")
    )
    s = summarize_policy("testdoc", policy_chunks)
    values = (
        [c["description"] for c in s.covered_services]
        + [e["service"] for e in s.excluded_services]
        + [p["service"] for p in s.prior_auth_services]
        + [c["amount"] for c in s.copayments]
        + [s.referral_requirements]
    )
    for v in values:
        assert v in source, v


def test_policy_summary_cites_sections(policy_chunks):
    s = summarize_policy("testdoc", policy_chunks)
    refs = {r["category"]: (r["page"], r["section"]) for r in s.source_references}
    assert refs["copayments"] == (2, "COPAYMENTS")
    assert refs["excluded_services"] == (4, "EXCLUSIONS AND LIMITATIONS")
    assert refs["prior_auth_services"] == (3, "PRIOR AUTHORIZATION REQUIREMENTS")
