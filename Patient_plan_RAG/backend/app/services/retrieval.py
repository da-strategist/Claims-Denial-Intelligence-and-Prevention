"""Keyword and hybrid retrieval over document chunks."""

import json
import math
import os
import re
from pathlib import Path

from ..models.policy import DocumentChunk

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
POLICY_DIR = Path(os.getenv("POLICY_DIR", str(BASE_DIR / "data" / "policies")))


_STOPWORDS = frozenset("""
a about am an and any are as at be been but by can could did do does doing for
from get got had has have how i if in into is it its me much my need of on or
our so than that the their them then there these they this to under us was we
were what when where which who why will with would you your
""".split())

# BM25 parameters and the weight of a query term matching the section heading
_K1 = 1.5
_B = 0.75
_HEADING_WEIGHT = 0.5
# Chunks matching less than this share of the query's weight are dropped, so
# off-topic questions yield "insufficient evidence" rather than noise.
_MIN_COVERAGE = 0.1


def _stem(token: str) -> str:
    """Minimal plural folding so 'visits' matches 'visit'."""
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def _tokenize(text: str) -> list[str]:
    """Lowercase, stopword-free, plural-folded tokens."""
    return [
        _stem(t) for t in re.findall(r"[a-z0-9]+", text.lower())
        if t not in _STOPWORDS
    ]


def _idf(chunks_tokens: list[set[str]]) -> dict[str, float]:
    n = len(chunks_tokens)
    df: dict[str, int] = {}
    for tokens in chunks_tokens:
        for t in tokens:
            df[t] = df.get(t, 0) + 1
    return {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}


def _registered_document_ids(policy_dir: Path) -> list[str] | None:
    """Document IDs in the registry, or None if there is no registry yet."""
    path = policy_dir / "_registry.json"
    if not path.exists():
        return None
    try:
        return [r["document_id"] for r in json.loads(path.read_text())]
    except Exception:
        return None


def load_chunks(
    chunk_dir: Path,
    document_id: str | None = None,
    policy_dir: Path | None = None,
) -> list[DocumentChunk]:
    """Load chunk JSON files from disk.

    Without a document_id, only documents listed in the registry are loaded,
    so orphaned chunk files (e.g. from a re-ingest) never surface in answers.
    """
    chunks: list[DocumentChunk] = []
    if not chunk_dir.exists():
        return chunks

    files = []
    if document_id:
        target = chunk_dir / f"{document_id}.json"
        if target.exists():
            files = [target]
    else:
        registered = _registered_document_ids(policy_dir or POLICY_DIR)
        if registered is None:
            files = sorted(chunk_dir.glob("*.json"))
        else:
            files = [chunk_dir / f"{d}.json" for d in registered]
            files = [f for f in files if f.exists()]

    for f in files:
        try:
            raw = json.loads(f.read_text())
            chunks.extend(DocumentChunk(**item) for item in raw)
        except Exception:
            continue
    return chunks


def retrieve(
    query: str,
    chunks: list[DocumentChunk],
    top_k: int = 5,
) -> list[tuple[DocumentChunk, float]]:
    """Retrieve top-k chunks ranked by BM25 (plus a section-heading boost).

    The returned score is not the BM25 value: it is the IDF-weighted share of
    query terms found in the chunk (0..1), which callers use as a confidence
    signal (> 0.3 → "supported").
    """
    query_tokens = set(_tokenize(query))
    if not query_tokens or not chunks:
        return []

    content_tokens = [_tokenize(c.content) for c in chunks]
    heading_tokens = [set(_tokenize(c.section_heading)) for c in chunks]
    idf = _idf([set(t) | h for t, h in zip(content_tokens, heading_tokens)])
    avg_len = sum(len(t) for t in content_tokens) / len(chunks) or 1.0
    # Terms absent from every chunk count at maximum IDF, so a question about
    # things the policy never mentions gets low coverage instead of being
    # judged only on its few common words.
    unseen_idf = math.log(1 + (len(chunks) + 0.5) / 0.5)
    query_weight = sum(idf.get(t, unseen_idf) for t in query_tokens)

    ranked = []
    for chunk, tokens, heading in zip(chunks, content_tokens, heading_tokens):
        tf: dict[str, int] = {}
        for t in tokens:
            if t in query_tokens:
                tf[t] = tf.get(t, 0) + 1
        norm = _K1 * (1 - _B + _B * len(tokens) / avg_len)
        bm25 = sum(idf[t] * f * (_K1 + 1) / (f + norm) for t, f in tf.items())
        bm25 += _HEADING_WEIGHT * sum(idf[t] for t in query_tokens & heading)
        if bm25 <= 0:
            continue
        coverage = sum(idf[t] for t in query_tokens & (set(tf) | heading)) / query_weight
        if coverage >= _MIN_COVERAGE:
            ranked.append((bm25, chunk, coverage))

    ranked.sort(key=lambda x: x[0], reverse=True)
    return [(c, cov) for _, c, cov in ranked[:top_k]]


def retrieve_for_policy(
    query: str,
    chunk_dir: Path,
    document_id: str | None = None,
    top_k: int = 5,
) -> list[tuple[DocumentChunk, float]]:
    """Convenience: load chunks and retrieve in one call."""
    chunks = load_chunks(chunk_dir, document_id)
    return retrieve(query, chunks, top_k)
