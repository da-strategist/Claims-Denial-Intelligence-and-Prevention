"""Tests for PDF extraction, heading detection, and chunking."""

import json
import re

import pytest

from backend.app.models.policy import DocumentStatus
from backend.app.services.document_processor import (
    _detect_section,
    chunk_text,
    process_document,
)
from backend.app.tests.conftest import POLICY_PDF


# ── Heading detection ────────────────────────────────────────────────

@pytest.mark.parametrize("line", [
    "PRIOR AUTHORIZATION REQUIREMENTS",
    "EXCLUSIONS AND LIMITATIONS",
    "DEFINITIONS",
    "Prior Authorization Requirements",
    "Exclusions and Limitations",
    "Summary of Benefits",
])
def test_detects_headings(line):
    assert _detect_section(line) == line


@pytest.mark.parametrize("line", [
    # label-prefixed body lines
    "Deductible: The amount a member pays for covered services before the plan begins to pay.",
    "PREVENTIVE CARE: Covered at 100% in-network with no deductible or copay. Includes annual",
    "EMERGENCY SERVICES: Emergency services are covered at in-network rates regardless of whether",
    # long all-caps disclaimer sentence
    "THIS IS A SYNTHETIC INSURANCE POLICY DOCUMENT CREATED FOR DEMONSTRATION AND",
    "Apex Health Insurance",
    # wrapped body text starting with a heading keyword
    "Coverage applies to dependents up to",
    "",
])
def test_rejects_body_lines(line):
    assert _detect_section(line) == ""


# ── Chunking (synthetic input) ───────────────────────────────────────

def _pages(*texts):
    return [{"page_number": i, "text": t} for i, t in enumerate(texts, start=1)]


def test_new_chunk_at_each_heading_with_own_label():
    chunks = chunk_text(_pages("COPAYMENTS\nSpecialist: $50\nEXCLUSIONS\nAcupuncture"), "d")
    assert [(c.section_heading, c.content) for c in chunks] == [
        ("COPAYMENTS", "COPAYMENTS\nSpecialist: $50"),
        ("EXCLUSIONS", "EXCLUSIONS\nAcupuncture"),
    ]


def test_consecutive_headings_stay_together_last_one_labels():
    chunks = chunk_text(_pages("COST-SHARING PROVISIONS\nANNUAL DEDUCTIBLE\nIndividual: $1,500"), "d")
    assert len(chunks) == 1
    assert chunks[0].section_heading == "ANNUAL DEDUCTIBLE"
    assert chunks[0].content.startswith("COST-SHARING PROVISIONS\n")


def test_long_section_splits_on_whole_lines_with_overlap():
    lines = [f"Line {i} " + "x" * 50 for i in range(40)]
    chunks = chunk_text(_pages("COVERED SERVICES\n" + "\n".join(lines)), "d",
                        chunk_size=400, chunk_overlap=100)
    assert len(chunks) > 1
    all_lines = {"COVERED SERVICES", *lines}
    for c in chunks:
        assert c.section_heading == "COVERED SERVICES"
        assert len(c.content) <= 400
        # every line in every chunk is a whole source line
        assert set(c.content.split("\n")) <= all_lines
    # each split chunk starts with the previous chunk's trailing line
    for prev, nxt in zip(chunks, chunks[1:]):
        assert nxt.content.split("\n")[0] == prev.content.split("\n")[-1]


def test_page_number_is_where_chunk_body_starts():
    chunks = chunk_text(_pages("COPAYMENTS\nSpecialist: $50", "EXCLUSIONS\nAcupuncture"), "d")
    assert [c.page_number for c in chunks] == [1, 2]


def test_cid_bullets_are_cleaned():
    chunks = chunk_text(_pages("EXCLUSIONS\n(cid:127) Acupuncture"), "d")
    assert chunks[0].content == "EXCLUSIONS\n• Acupuncture"


def test_chunk_ids_are_deterministic():
    pages = _pages("COPAYMENTS\nSpecialist: $50\nEXCLUSIONS\nAcupuncture")
    assert [c.chunk_id for c in chunk_text(pages, "d")] == [c.chunk_id for c in chunk_text(pages, "d")]


def test_empty_pages_produce_no_chunks():
    assert chunk_text(_pages("", ""), "d") == []


# ── Chunking (synthetic policy) ──────────────────────────────────────

def test_policy_chunks_never_start_mid_word(policy_pages, policy_chunks):
    source_lines = {
        line.replace("(cid:127)", "•").strip()
        for p in policy_pages for line in p["text"].split("\n")
    }
    for c in policy_chunks:
        assert c.content.split("\n")[0] in source_lines, c.content[:60]


def test_policy_disclaimer_banner_is_not_a_section_label(policy_chunks):
    assert not any(c.section_heading.startswith("THIS IS A SYNTHETIC") for c in policy_chunks)


def test_policy_sections_are_labelled(policy_chunks):
    by_section = {c.section_heading for c in policy_chunks}
    for expected in ["ANNUAL DEDUCTIBLE", "COPAYMENTS", "COVERED SERVICES",
                     "PRIOR AUTHORIZATION REQUIREMENTS", "EXCLUSIONS AND LIMITATIONS",
                     "APPEALS AND GRIEVANCES", "DEFINITIONS"]:
        assert expected in by_section
    specialist = next(c for c in policy_chunks if "Specialist Office Visit" in c.content)
    assert specialist.section_heading == "COPAYMENTS"


# ── process_document ─────────────────────────────────────────────────

def test_process_document_uses_given_id_and_overwrites(tmp_path):
    if not POLICY_PDF.exists():
        pytest.skip("synthetic policy PDF missing")
    for _ in range(2):
        doc, chunks = process_document(POLICY_PDF, tmp_path, document_id="fixed123")
    assert doc.status == DocumentStatus.COMPLETED
    assert doc.document_id == "fixed123"
    assert [p.name for p in tmp_path.iterdir()] == ["fixed123.json"]
    saved = json.loads((tmp_path / "fixed123.json").read_text())
    assert len(saved) == doc.chunk_count == len(chunks)


def test_process_document_generates_id_when_not_given(tmp_path):
    if not POLICY_PDF.exists():
        pytest.skip("synthetic policy PDF missing")
    doc, _ = process_document(POLICY_PDF, tmp_path)
    assert re.fullmatch(r"[0-9a-f]{12}", doc.document_id)


def test_process_document_marks_unreadable_file_failed(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    doc, chunks = process_document(bad, tmp_path / "chunks")
    assert doc.status == DocumentStatus.FAILED
    assert doc.error_message
    assert chunks == []
