"""Score the app on the validation set against the agreed pass marks.

    python -m backend.app.tests.validation_eval            # report
    python -m backend.app.tests.validation_eval --details  # every failure

The validation set (synthetic_data/validation) is kept apart from the
regression eval and is not used to tune the app. Documents go through the
real pipeline (including OCR) into a temporary folder; questions go through
the same chat answer the app gives, in demo mode: single-plan questions with
that plan selected, several-plan questions across the person's plans.
"""

import argparse
import asyncio
import re
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from backend.app.services import ocr, rag, registry, retrieval, suggestions
from backend.app.services.document_processor import process_document
from synthetic_data.validation.ground_truth import norm, problems
from synthetic_data.validation.questions import METADATA, QUESTIONS

VALIDATION_DIR = Path(__file__).resolve().parents[3] / "data" / "validation"

# Agreed with the user 2026-10-21 (before any results were seen)
PASS_MARKS = {
    "cited_section": 0.95,
    "answer_text": 0.95,
    "abstention": 0.95,
    "plan_details": 1.00,
}
ZERO_TOLERANCE = ("invented_amounts", "wrong_plan_amounts")

_AMOUNT_RE = re.compile(r"\$\d[\d,]*(?:\.\d+)?")


@dataclass
class Result:
    counts: dict = field(default_factory=lambda: {k: [0, 0] for k in (
        "cited_section", "answer_text", "abstention", "plan_details", "differences")})
    invented_amounts: list = field(default_factory=list)
    wrong_plan_amounts: list = field(default_factory=list)
    by_category: dict = field(default_factory=dict)
    failures: list = field(default_factory=list)

    def tally(self, metric: str, ok: bool, why: str = "") -> None:
        self.counts[metric][1] += 1
        self.counts[metric][0] += ok
        if not ok and why:
            self.failures.append(f"[{metric}] {why}")


def _amounts(text: str) -> set[str]:
    return {a.replace(",", "") for a in _AMOUNT_RE.findall(text)}


def _ingest(tmp: Path) -> tuple[dict[str, str], dict[str, str], Path]:
    """Process every validation PDF; returns (filename → document_id,
    document_id → full chunk text, chunk dir) and writes a temporary registry."""
    chunk_dir = tmp / "chunks"
    entries, ids, texts = [], {}, {}
    for pdf in sorted(VALIDATION_DIR.glob("*.pdf")):
        doc, chunks = process_document(pdf, chunk_dir, metadata={"owner": "validator"})
        entries.append(doc.model_dump(mode="json"))
        ids[pdf.name] = doc.document_id
        texts[doc.document_id] = " ".join(c.content for c in chunks)
    registry.POLICY_DIR = retrieval.POLICY_DIR = tmp  # retrieval reads the registry too
    registry.save(entries)
    return ids, texts, chunk_dir


def run() -> Result:
    if found := problems():
        sys.exit("Fix the ground truth first:\n" + "\n".join(found))
    if not ocr.available():
        print("Note: OCR is unavailable, so the scanned questions will fail.", file=sys.stderr)
    res = Result()
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        ids, texts, chunk_dir = _ingest(tmp)
        by_id = {e["document_id"]: e for e in registry.load()}

        for filename, expected in METADATA.items():
            got = by_id[ids[filename]]
            for key, want in expected.items():
                value = got.get(key) or ""
                value = value.isoformat() if isinstance(value, date) else str(value)
                ok = (norm(want) in norm(value)) if key in ("insurer_name", "plan_name") else value == want
                res.tally("plan_details", ok, f"{filename} {key}: got {value!r}, want {want!r}")

        for q in QUESTIONS:
            scope = [ids[d] for d in q["docs"]]
            single = len(scope) == 1
            resp = asyncio.run(rag.answer_question(
                q["question"], chunk_dir, document_id=scope[0] if single else None,
                mode="demo", allowed_ids=set(scope), audience=suggestions.MEMBER))
            shown = resp.answer + " " + " ".join(p.quote for p in resp.policy_says)
            text = norm(shown)
            cat = res.by_category.setdefault(q["category"], [0, 0])
            brief = f"{q['id']} {q['question']!r} -> {resp.answer[:160]!r}"

            if q["category"] == "abstain":
                ok = resp.confidence == "insufficient_evidence"
                res.tally("abstention", ok, f"{brief} (should say it isn't in the document)")
            else:
                hits = [norm(p) in text for p in q["phrases"]]
                ok = all(hits) if q.get("all") else any(hits)
                res.tally("answer_text", ok, f"{brief} (want: {q['expected']})")
                if single and q["category"] != "multi_plan":
                    top = resp.citations[0].section if resp.citations else "(nothing cited)"
                    sec_ok = any(s.lower() in top.lower() for s in q["sections"])
                    res.tally("cited_section", sec_ok, f"{q['id']} cited {top!r}, want {q['sections']}")
            cat[0] += ok
            cat[1] += 1

            scope_amounts = set().union(*(_amounts(texts[d]) for d in scope))
            if invented := _amounts(resp.answer) - scope_amounts:
                res.invented_amounts.append(f"{q['id']}: {sorted(invented)}")
            if bad := [f for f in q.get("forbidden", []) if norm(f) in text]:
                res.wrong_plan_amounts.append(f"{q['id']}: {bad} in {resp.answer[:120]!r}")
            if q.get("differs"):
                flagged = any(q["differs"].lower() in d.topic.lower() for d in resp.differences)
                res.tally("differences", flagged, f"{q['id']} difference {q['differs']!r} not flagged")
            if q.get("same"):
                res.tally("differences", not resp.differences,
                          f"{q['id']} flagged a difference where the plans agree")
    return res


def report(res: Result, details: bool = False) -> bool:
    print("Validation set:", len(QUESTIONS), "questions,", len(METADATA), "documents\n")
    print(f"{'measure':28} {'score':>10} {'pass mark':>10}  result")
    passed = True
    for metric, mark in PASS_MARKS.items():
        ok, n = res.counts[metric]
        share = ok / n if n else 1.0
        good = share >= mark
        passed &= good
        print(f"{metric:28} {ok:>4}/{n:<4} {share:>5.0%} {mark:>9.0%}  {'PASS' if good else 'FAIL'}")
    for metric in ZERO_TOLERANCE:
        items = getattr(res, metric)
        passed &= not items
        print(f"{metric:28} {len(items):>10} {'0':>10}  {'PASS' if not items else 'FAIL'}")
    ok, n = res.counts["differences"]
    print(f"{'differences flagged (info)':28} {ok:>4}/{n:<4}")
    print("\nBy question type:", ", ".join(f"{k} {v[0]}/{v[1]}" for k, v in sorted(res.by_category.items())))
    print(f"\nOverall: {'PASS' if passed else 'FAIL'}")
    if details:
        for line in res.failures + res.invented_amounts + res.wrong_plan_amounts:
            print(" -", line)
    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--details", action="store_true", help="list every failure")
    report(run(), parser.parse_args().details)
