"""Demo-mode answers quote the best-matching paragraphs verbatim."""

from backend.app.models.policy import DocumentChunk
from backend.app.services.rag import _QUOTE_MAX_CHARS, _build_demo_answer

COVERED = DocumentChunk(
    chunk_id="c1", document_id="d", page_number=2, section_heading="COVERED SERVICES",
    content="COVERED SERVICES\nThe following services are covered under this plan:\n"
            "PREVENTIVE CARE: Covered at 100% in-network with no deductible.\n"
            "REHABILITATION SERVICES: Physical therapy covered at 80%, limited to 30 visits "
            "per therapy type per calendar year.")
EXCLUDED = DocumentChunk(
    chunk_id="c2", document_id="d", page_number=4, section_heading="EXCLUSIONS",
    content="EXCLUSIONS\n• Acupuncture, naturopathy, and homeopathy\n• Cosmetic surgery")


def _answer(question, chunks, query=None):
    return _build_demo_answer(question, [(c, 0.8) for c in chunks], query)


def test_quotes_the_matching_paragraph_with_page_and_section():
    answer, _ = _answer("How many physical therapy visits are covered?", [COVERED, EXCLUDED])
    assert ("“REHABILITATION SERVICES: Physical therapy covered at 80%, limited to 30 visits "
            "per therapy type per calendar year.”\n— page 2, COVERED SERVICES") in answer
    assert answer.index("REHABILITATION") < answer.index("⚠️")


def test_quotes_can_come_from_the_same_chunk_or_lower_ranked_chunks():
    answer, _ = _answer("Is acupuncture covered?", [COVERED, EXCLUDED])
    assert "“Acupuncture, naturopathy, and homeopathy”\n— page 4, EXCLUSIONS" in answer


def test_heading_lines_are_never_quoted():
    answer, _ = _answer("What are the exclusions?", [EXCLUDED])
    assert "“EXCLUSIONS”" not in answer


def test_citation_excerpt_is_the_chunks_best_paragraph():
    _, citations = _answer("Is acupuncture covered?", [COVERED, EXCLUDED])
    assert citations[1].excerpt == "Acupuncture, naturopathy, and homeopathy"
    assert citations[0].page_number == 2  # citation order follows retrieval


def test_query_with_context_steers_the_quote():
    question = "How many visits does it include?"
    answer, _ = _answer(question, [COVERED], query="Is physical therapy covered? " + question)
    assert "limited to 30 visits" in answer


def test_long_paragraph_is_trimmed_to_matching_sentences():
    filler = "This sentence is about something else entirely. " * 12
    chunk = DocumentChunk(chunk_id="c3", document_id="d", page_number=1, section_heading="X",
                          content=f"X\n{filler}Hospice care is covered at 100%. {filler}")
    answer, _ = _answer("Is hospice care covered?", [chunk])
    quote = answer.split("“")[1].split("”")[0]
    assert "Hospice care is covered at 100%." in quote
    assert len(quote) <= _QUOTE_MAX_CHARS + 2
    assert "something else entirely" not in quote


def test_no_passages_gives_insufficient_evidence_template():
    answer, citations = _answer("Is anything covered?", [])
    assert "could not find sufficient evidence" in answer and citations == []
