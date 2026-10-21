"""Keyword and hybrid retrieval over document chunks."""

import json
import math
import os
import re
from pathlib import Path

from ..models.common import DOCUMENT_ID_PATTERN
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
# Weight of a query term matching a line label ("Deductible: ...", or a table
# row "Specialist visit $65 copay"): "what is X" questions are usually
# answered by the line labelled X.
_LABEL_WEIGHT = 0.3  # flat 0.15–0.3 on the evals; 0.5 hurts Apex (glossary labels)
_LABEL_MAX_WORDS = 6
_LABEL_RE = re.compile(r"^\s*(?:•\s*)?([^:$]{2,60}?)\s*(?::\s|\$\d)")
# Chunks matching less than this share of the query's weight are dropped, so
# off-topic questions yield "insufficient evidence" rather than noise.
_MIN_COVERAGE = 0.1


# Curated insurance word families, folded to one token on both sides (query
# and policy text). Kept small and explicit rather than a general stemmer;
# each family earns its place on the eval. Folding approval / authorization /
# precertification together was tried and dropped: those words are so common
# in policies that merging them made glossary entries outrank the answer.
_WORD_FAMILIES = {
    "deny": ("denied", "denial", "denials", "denies", "denying"),
    "child": ("children", "kids", "kid", "pediatric"),
    "decide": ("decision", "decisions", "decided", "decides"),
}
_FAMILY_OF = {word: canon for canon, words in _WORD_FAMILIES.items() for word in words}

# Different policies name the same process differently. Rather than folding
# these words together in the policy text (see above), a question using one
# name is rewritten to the name the policy in scope actually uses — only when
# the question's own wording is absent from it.
_CONCEPTS = [
    ("prior authorization", "prior authorisation", "preauthorization", "pre-authorization",
     "precertification", "pre-certification", "advance approval", "prior approval"),
]
_PRIOR_AUTH_SHORT = re.compile(r"\bprior[- ]auth\b", re.I)


def adapt_vocabulary(query: str, chunks: list[DocumentChunk]) -> str:
    """Rewrite a concept in the query to the wording the chunks use."""
    text = query.lower()
    if _PRIOR_AUTH_SHORT.search(text):
        text = _PRIOR_AUTH_SHORT.sub("prior authorization", text)
    for variants in _CONCEPTS:
        used = next((v for v in variants if v in text), None)
        if used is None:
            continue
        # headings count three times: a section named after the process is the answer
        presence = {v: sum(3 * c.section_heading.lower().count(v)
                           + (c.content_lower or c.content.lower()).count(v) for c in chunks)
                    for v in variants}
        if presence[used]:
            return query
        best = max(variants, key=lambda v: presence[v])
        if presence[best]:
            return text.replace(used, best)
    return query


def _stem(token: str) -> str:
    """Word families, then minimal plural folding ('visits' → 'visit',
    'therapies' → 'therapy', 'applied' → 'apply')."""
    if token in _FAMILY_OF:
        return _FAMILY_OF[token]
    if len(token) > 4 and token.endswith(("ies", "ied")):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def _tokenize(text: str) -> list[str]:
    """Lowercase, stopword-free, family- and plural-folded tokens."""
    return [
        _stem(t) for t in re.findall(r"[a-z0-9]+", text.lower())
        if t not in _STOPWORDS
    ]


def _labels(text: str) -> set[str]:
    """Tokens of short line labels: text before ':' or before a $ amount."""
    tokens: set[str] = set()
    for line in text.split("\n"):
        m = _LABEL_RE.match(line)
        if m and len(m.group(1).split()) <= _LABEL_MAX_WORDS:
            tokens.update(_tokenize(m.group(1)))
    return tokens


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
    allowed_ids: set[str] | None = None,
) -> list[DocumentChunk]:
    """Load chunk JSON files from disk.

    Without a document_id, only documents listed in the registry are loaded,
    so orphaned chunk files (e.g. from a re-ingest) never surface in answers,
    and only those in `allowed_ids` when given (the documents a user may see).
    """
    chunks: list[DocumentChunk] = []
    if not chunk_dir.exists():
        return chunks

    files = []
    if document_id:
        if not re.fullmatch(DOCUMENT_ID_PATTERN, document_id):
            return chunks
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
        if allowed_ids is not None:
            files = [f for f in files if f.stem in allowed_ids]

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
    """Retrieve top-k chunks ranked by BM25 plus section-heading and line-label boosts.

    The returned score is not the BM25 value: it is the IDF-weighted share of
    query terms found in the chunk (0..1), which callers use as a confidence
    signal (> 0.3 → "supported").
    """
    query_tokens = set(_tokenize(query))
    if not query_tokens or not chunks:
        return []

    content_tokens = [_tokenize(c.content) for c in chunks]
    heading_tokens = [set(_tokenize(c.section_heading)) for c in chunks]
    label_tokens = [_labels(c.content) for c in chunks]
    idf = _idf([set(t) | h for t, h in zip(content_tokens, heading_tokens)])
    avg_len = sum(len(t) for t in content_tokens) / len(chunks) or 1.0
    # Terms absent from every chunk count at maximum IDF, so a question about
    # things the policy never mentions gets low coverage instead of being
    # judged only on its few common words.
    unseen_idf = math.log(1 + (len(chunks) + 0.5) / 0.5)
    query_weight = sum(idf.get(t, unseen_idf) for t in query_tokens)

    ranked = []
    for chunk, tokens, heading, labels in zip(chunks, content_tokens, heading_tokens, label_tokens):
        tf: dict[str, int] = {}
        for t in tokens:
            if t in query_tokens:
                tf[t] = tf.get(t, 0) + 1
        norm = _K1 * (1 - _B + _B * len(tokens) / avg_len)
        bm25 = sum(idf[t] * f * (_K1 + 1) / (f + norm) for t, f in tf.items())
        bm25 += _HEADING_WEIGHT * sum(idf[t] for t in query_tokens & heading)
        bm25 += _LABEL_WEIGHT * sum(idf[t] for t in query_tokens & labels)
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
    allowed_ids: set[str] | None = None,
) -> list[tuple[DocumentChunk, float]]:
    """Convenience: load chunks and retrieve in one call."""
    chunks = load_chunks(chunk_dir, document_id, allowed_ids=allowed_ids)
    return retrieve(query, chunks, top_k)
