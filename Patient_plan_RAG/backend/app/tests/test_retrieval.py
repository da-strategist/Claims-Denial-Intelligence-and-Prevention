"""Tests for chunk loading and BM25 retrieval, including a regression eval."""

import json
import re

import pytest

from backend.app.models.policy import DocumentChunk
from backend.app.services.retrieval import load_chunks, retrieve

# (question, phrases any of which answers it). Baseline before BM25 and
# section-aware chunking: 2/18 top-1, 10/18 top-3.
EVAL_CASES = [
    ("Does my plan cover an MRI and is prior authorization required?",
     ["Advanced imaging (MRI", "Advanced diagnostic imaging (MRI"]),
    ("How much is a specialist visit copay?", ["Specialist Office Visit: $50"]),
    ("What is the family out-of-pocket maximum in network?", ["Family In-Network: $12,000"]),
    ("What is the individual deductible?", ["Individual In-Network: $1,500"]),
    ("How do I appeal a denied claim?", ["Appeals must be filed within 180"]),
    ("Is cosmetic surgery covered?", ["Cosmetic surgery or procedures"]),
    ("What documents are needed for a prior authorization request?", ["Form PA-100"]),
    ("How long does an authorization decision take?", ["within 5 business days for standard requests"]),
    ("What is the copay for outpatient mental health visits?", ["Outpatient mental health visits have a $40"]),
    ("How much do Tier 4 specialty drugs cost?", ["Tier 4 (Specialty): 25% coinsurance"]),
    ("Are emergency room visits covered out of network?",
     ["Emergency services are covered at in-network rates", "Emergency Room Visit: $250"]),
    ("How many physical therapy visits are covered per year?", ["limited to 30 visits per therapy type"]),
    ("Is acupuncture covered?", ["Acupuncture, naturopathy"]),
    ("Do I need a referral to see a specialist?", ["does not require referrals"]),
    ("Is genetic testing covered?", ["Genetic testing requires prior authorization", "Genetic testing"]),
    ("What does coinsurance mean?", ["Coinsurance: The percentage"]),
    ("How many days in a skilled nursing facility are covered?", ["limited to 60 days per calendar year"]),
    ("Is hospice care covered?", ["HOSPICE CARE: Covered at 100%"]),
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s)


def _rank(question, phrases, chunks, top_k=3):
    hits = retrieve(question, chunks, top_k=top_k)
    for i, (chunk, _) in enumerate(hits, start=1):
        if any(_norm(p) in _norm(chunk.content) for p in phrases):
            return i
    return None


# ── Regression eval over the synthetic policy ────────────────────────

@pytest.mark.parametrize("question,phrases", EVAL_CASES, ids=[q for q, _ in EVAL_CASES])
def test_answer_in_top_3(question, phrases, policy_chunks):
    assert _rank(question, phrases, policy_chunks) is not None


def test_top_1_accuracy(policy_chunks):
    top1 = sum(_rank(q, p, policy_chunks) == 1 for q, p in EVAL_CASES)
    assert top1 >= 17, f"top-1 {top1}/{len(EVAL_CASES)}"


# ── Scores and filtering ─────────────────────────────────────────────

def test_scores_are_coverage_fractions(policy_chunks):
    hits = retrieve("Does my plan cover an MRI and is prior authorization required?", policy_chunks)
    assert hits
    assert all(0.1 <= score <= 1.0 for _, score in hits)
    assert max(score for _, score in hits) > 0.3


@pytest.mark.parametrize("question", [
    "Is laser tattoo removal covered?",
    "what is the weather on mars",
])
def test_off_topic_questions_return_nothing(question, policy_chunks):
    assert retrieve(question, policy_chunks) == []


def test_off_topic_partial_match_is_low_confidence(policy_chunks):
    hits = retrieve("Will the plan pay for my dog to get a dental implant on Mars?", policy_chunks)
    assert all(score <= 0.3 for _, score in hits)


@pytest.mark.parametrize("query", ["", "is the and of", "???"])
def test_empty_or_stopword_queries_return_nothing(query, policy_chunks):
    assert retrieve(query, policy_chunks) == []


def test_no_chunks_returns_nothing():
    assert retrieve("MRI", []) == []


def test_top_k_is_respected(policy_chunks):
    assert len(retrieve("prior authorization required", policy_chunks, top_k=2)) == 2


def test_plural_query_matches_singular_text():
    chunk = DocumentChunk(chunk_id="c", document_id="d", content="One visit per year.")
    other = DocumentChunk(chunk_id="o", document_id="d", content="Unrelated text here.")
    assert [c.chunk_id for c, _ in retrieve("visits", [chunk, other])] == ["c"]


def test_section_heading_boosts_ranking():
    body = "Covered at 80% after deductible."
    plain = DocumentChunk(chunk_id="plain", document_id="d", content=body)
    headed = DocumentChunk(chunk_id="headed", document_id="d", content=body,
                           section_heading="DIAGNOSTIC IMAGING")
    filler = DocumentChunk(chunk_id="f", document_id="d", content="Something else entirely.")
    hits = retrieve("imaging covered", [plain, headed, filler])
    assert hits[0][0].chunk_id == "headed"


# ── load_chunks ──────────────────────────────────────────────────────

def _write_chunks(chunk_dir, document_id):
    chunk = DocumentChunk(chunk_id=f"{document_id}-0", document_id=document_id, content="text")
    (chunk_dir / f"{document_id}.json").write_text(json.dumps([chunk.model_dump()]))


@pytest.fixture
def dirs(tmp_path):
    chunk_dir, policy_dir = tmp_path / "chunks", tmp_path / "policies"
    chunk_dir.mkdir()
    policy_dir.mkdir()
    for doc_id in ("registered", "orphan"):
        _write_chunks(chunk_dir, doc_id)
    return chunk_dir, policy_dir


def _doc_ids(chunks):
    return sorted({c.document_id for c in chunks})


def test_load_chunks_ignores_unregistered_files(dirs):
    chunk_dir, policy_dir = dirs
    (policy_dir / "_registry.json").write_text(json.dumps([{"document_id": "registered"}]))
    assert _doc_ids(load_chunks(chunk_dir, policy_dir=policy_dir)) == ["registered"]


def test_load_chunks_skips_registered_doc_without_file(dirs):
    chunk_dir, policy_dir = dirs
    (policy_dir / "_registry.json").write_text(
        json.dumps([{"document_id": "registered"}, {"document_id": "missing"}]))
    assert _doc_ids(load_chunks(chunk_dir, policy_dir=policy_dir)) == ["registered"]


def test_load_chunks_without_registry_loads_all(dirs):
    chunk_dir, policy_dir = dirs
    assert _doc_ids(load_chunks(chunk_dir, policy_dir=policy_dir)) == ["orphan", "registered"]


def test_load_chunks_by_id_bypasses_registry(dirs):
    chunk_dir, policy_dir = dirs
    (policy_dir / "_registry.json").write_text(json.dumps([{"document_id": "registered"}]))
    assert _doc_ids(load_chunks(chunk_dir, "orphan", policy_dir=policy_dir)) == ["orphan"]


def test_load_chunks_unknown_id_or_missing_dir(dirs, tmp_path):
    chunk_dir, _ = dirs
    assert load_chunks(chunk_dir, "nope") == []
    assert load_chunks(tmp_path / "does-not-exist") == []


@pytest.mark.parametrize("query,text", [
    ("Was my claim denied?", "Appeals must follow a denial notice."),
    ("Are glasses covered for my child?", "Eye exams for children are covered."),
    ("How long does a decision take?", "We decide most requests within 14 days."),
    ("Are therapies covered?", "Physical therapy is covered."),
])
def test_word_families_and_plurals_match(query, text):
    chunk = DocumentChunk(chunk_id="c", document_id="d", content=text)
    other = DocumentChunk(chunk_id="o", document_id="d", content="Unrelated words only.")
    assert [c.chunk_id for c, _ in retrieve(query, [chunk, other])] == ["c"]


def test_approval_and_authorization_stay_distinct():
    # folding them together made glossary entries outrank answers (see retrieval.py)
    from backend.app.services.retrieval import _tokenize
    assert _tokenize("approval") != _tokenize("authorization")
