"""Multi-policy eval: metadata, retrieval, coverage, and summary per policy.

Scores the current pipeline against synthetic_data/scenarios/policy_scenarios.py.
Run for a scorecard:
    python -m backend.app.tests.policy_eval
test_policy_eval.py turns the scores into regression thresholds.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from backend.app.services.coverage_assessor import assess_coverage
from backend.app.services.document_processor import (
    chunk_text,
    extract_policy_metadata,
    extract_text_from_pdf,
)
from backend.app.services.policy_summarizer import summarize_policy
from backend.app.services.rag import _build_demo_answer
from backend.app.services.retrieval import retrieve
from synthetic_data.scenarios.policy_scenarios import SCENARIOS

POLICY_DIR = Path(__file__).resolve().parents[3] / "data" / "policies"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("(cid:127)", "•"))


@dataclass
class PolicyScore:
    name: str
    metadata: tuple[int, int] = (0, 0)
    retrieval_top1: tuple[int, int] = (0, 0)
    retrieval_top3: tuple[int, int] = (0, 0)
    section_top1: tuple[int, int] = (0, 0)
    answer_text: tuple[int, int] = (0, 0)
    coverage: tuple[int, int] = (0, 0)
    summary: tuple[int, int] = (0, 0)
    failures: list[str] = field(default_factory=list)


def _field_matches(value, needles: list[str]) -> bool:
    """Some item of a list field (or the field's whole text) has every needle."""
    if isinstance(value, list):
        items = [" ".join(str(v) for v in item.values()) if isinstance(item, dict) else str(item)
                 for item in value]
    elif isinstance(value, dict):
        items = [" ".join(str(v) for v in value.values())]
    else:
        items = [str(value or "")]
    return any(all(n in _norm(item) for n in needles) for item in items)


def validate_scenarios() -> list[str]:
    """Ground-truth phrases that do not occur in their policy's text."""
    problems = []
    for filename, spec in SCENARIOS.items():
        text = _norm(" ".join(p["text"] for p in extract_text_from_pdf(POLICY_DIR / filename)))
        for question, phrases, _ in spec["retrieval"]:
            if not any(_norm(p) in text for p in phrases):
                problems.append(f"{filename}: no phrase found for {question!r}")
        for fld, needles in spec["summary"]:
            for n in needles:
                if n not in text:
                    problems.append(f"{filename}: summary needle {n!r} ({fld}) not in text")
    return problems


def score_policy(filename: str) -> PolicyScore:
    spec = SCENARIOS[filename]
    pages = extract_text_from_pdf(POLICY_DIR / filename)
    chunks = chunk_text(pages, "eval")
    score = PolicyScore(filename)

    meta = {k: v.isoformat() if isinstance(v, date) else v
            for k, v in extract_policy_metadata(pages).items()}
    ok = 0
    for key, expected in spec["metadata"].items():
        if meta.get(key) == expected:
            ok += 1
        else:
            score.failures.append(f"metadata {key}: got {meta.get(key)!r}, want {expected!r}")
    score.metadata = (ok, len(spec["metadata"]))

    top1 = top3 = section = answered = 0
    for question, phrases, sections in spec["retrieval"]:
        # demo-mode answer text (chat retrieves top 5) must quote the answer
        answer, _ = _build_demo_answer(question, retrieve(question, chunks, top_k=5))
        if any(_norm(p) in _norm(answer) for p in phrases):
            answered += 1
        else:
            score.failures.append(f"answer text lacks the answer: {question!r}")
        hits = retrieve(question, chunks, top_k=3)
        ranks = [i for i, (c, _) in enumerate(hits, 1)
                 if any(_norm(p) in _norm(c.content) for p in phrases)]
        top1 += bool(ranks) and ranks[0] == 1
        top3 += bool(ranks)
        got = (hits[0][0].section_heading or "(no section)") if hits else "nothing"
        right_section = any(sec.lower() in got.lower() for sec in sections)
        section += right_section
        if not ranks or ranks[0] != 1 or not right_section:
            score.failures.append(
                f"retrieval rank {ranks[0] if ranks else '-'}, section "
                f"{'ok' if right_section else 'WRONG'}: {question!r} -> {got[:50]}")
    n = len(spec["retrieval"])
    score.retrieval_top1, score.retrieval_top3 = (top1, n), (top3, n)
    score.section_top1 = (section, n)
    score.answer_text = (answered, n)

    ok = 0
    for service, classification, prior_auth in spec["coverage"]:
        result = assess_coverage(service, "", chunks)
        got = (result.classification.value, result.prior_auth_required)
        if got == (classification, prior_auth):
            ok += 1
        else:
            score.failures.append(f"coverage {service}: got {got}, want {(classification, prior_auth)}")
    score.coverage = (ok, len(spec["coverage"]))

    summary = summarize_policy("eval", chunks).model_dump()
    ok = 0
    for fld, needles in spec["summary"]:
        if _field_matches(summary[fld], needles):
            ok += 1
        else:
            score.failures.append(f"summary {fld}: no item with {needles}")
    score.summary = (ok, len(spec["summary"]))
    return score


def score_all() -> list[PolicyScore]:
    return [score_policy(f) for f in SCENARIOS]


def _fmt(pair: tuple[int, int]) -> str:
    return f"{pair[0]}/{pair[1]}"


if __name__ == "__main__":
    problems = validate_scenarios()
    for p in problems:
        print("SCENARIO ERROR:", p)
    scores = score_all()
    cols = ("metadata", "retrieval_top1", "retrieval_top3", "section_top1", "answer_text",
            "coverage", "summary")
    print(f"{'policy':<45}" + "".join(f"{c:>15}" for c in cols))
    totals = {c: [0, 0] for c in cols}
    for s in scores:
        print(f"{s.name:<45}" + "".join(f"{_fmt(getattr(s, c)):>15}" for c in cols))
        for c in cols:
            totals[c][0] += getattr(s, c)[0]
            totals[c][1] += getattr(s, c)[1]
    print(f"{'TOTAL':<45}" + "".join(f"{_fmt(tuple(totals[c])):>15}" for c in cols))
    for s in scores:
        if s.failures:
            print(f"\n{s.name}")
            for f in s.failures:
                print("  -", f)
