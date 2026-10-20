"""Evaluate the clarification assistant on the billing questions in assistant_cases.py.

    uv run python -m app.evals.assistant          # retrieval only: free, offline
    uv run python -m app.evals.assistant --llm    # also grade Claude's answers (needs a key)

Retrieval: recall (every expected source retrieved) and MRR (how high the first one ranks).
Answers: accuracy (states the expected facts, or says the tables don't answer it), citation
validity (cites only sources it was given), and grounding (cites the expected sources).
"""

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from app.data.knowledge import KnowledgeBase
from app.data.repository import DEFAULT_DATA_DIR
from app.evals.assistant_cases import CASES, EvalCase
from app.services.assistant import (
    DEFAULT_MODEL,
    AnswerWriter,
    ClaudeWriter,
    Retriever,
    answer_question,
    cited_labels,
)

# How a correct answer says the reference tables don't cover the question
DECLINES = re.compile(
    r"\b(not (?:listed|included|specified|available|contain|provide|state|cover)\w*"
    r"|doesn'?t (?:list|include|specify|contain|state|provide)|does not (?:list|include|"
    r"specify|contain|state|provide)|no (?:information|record|data)|cannot (?:determine|confirm)"
    r"|isn'?t (?:listed|included|in))",
    re.I,
)


@dataclass
class Result:
    case: EvalCase
    retrieved: list[str]
    recall: bool
    reciprocal_rank: float
    answer: str | None = None
    accurate: bool | None = None
    valid_citations: bool | None = None
    grounded: bool | None = None


def evaluate(case: EvalCase, retriever: Retriever, writer: AnswerWriter | None) -> Result:
    matches = retriever.retrieve(case.question, case.facts, case.topic)
    retrieved = [m.source.reference_id for m in matches]
    ranks = [retrieved.index(s) + 1 for s in case.expected_sources if s in retrieved]
    result = Result(
        case,
        retrieved,
        recall=all(s in retrieved for s in case.expected_sources),
        reciprocal_rank=1 / min(ranks) if ranks else 0.0,
    )
    if writer is None:
        return result

    answer = answer_question(case.question, case.facts, case.topic, retriever, writer)
    text = answer.answer.lower()
    labels = {s.label for s in answer.sources}
    expected_labels = {s.label for s in answer.sources if s.reference_id in case.expected_sources}
    cited = cited_labels(answer.answer)
    result.answer = answer.answer
    result.accurate = all(term.lower() in text for term in case.answer_terms) and (
        not case.unanswerable or bool(DECLINES.search(answer.answer))
    )
    result.valid_citations = bool(cited) and cited <= labels
    result.grounded = expected_labels <= cited
    return result


def _rate(values: list[bool]) -> str:
    return f"{sum(values)}/{len(values)} ({sum(values) / len(values):.0%})" if values else "n/a"


def report(results: list[Result], show_answers: bool) -> None:
    for r in results:
        marks = "retrieval " + ("ok  " if r.recall else "MISS")
        if r.answer is not None:
            marks += "".join(
                f" | {name} {'ok' if value else 'FAIL'}"
                for name, value in [
                    ("answer", r.accurate),
                    ("citations", r.valid_citations),
                    ("grounded", r.grounded),
                ]
            )
        print(f"{r.case.id:36} {marks}")
        if not r.recall:
            print(f"    expected {list(r.case.expected_sources)}, retrieved {r.retrieved}")
        if r.answer is not None and (show_answers or not (r.accurate and r.grounded)):
            print("    " + r.answer.replace("\n", "\n    "))

    print()
    print(f"Retrieval recall      {_rate([r.recall for r in results])}")
    mrr = sum(r.reciprocal_rank for r in results) / len(results)
    print(f"Retrieval MRR         {mrr:.2f}")
    graded = [r for r in results if r.answer is not None]
    if graded:
        print(f"Answer accuracy       {_rate([bool(r.accurate) for r in graded])}")
        print(f"Valid citations       {_rate([bool(r.valid_citations) for r in graded])}")
        print(f"Cites expected source {_rate([bool(r.grounded) for r in graded])}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--llm", action="store_true", help="also grade Claude's answers")
    parser.add_argument("--model", default=os.environ.get("RCM_ASSISTANT_MODEL", DEFAULT_MODEL))
    parser.add_argument("--show-answers", action="store_true")
    parser.add_argument("--case", help="run only cases whose id contains this")
    args = parser.parse_args()

    if args.llm and not os.environ.get("ANTHROPIC_API_KEY"):
        print("--llm needs ANTHROPIC_API_KEY", file=sys.stderr)
        return 2
    data_dir = Path(os.environ.get("RCM_DATA_DIR", DEFAULT_DATA_DIR))
    retriever = Retriever(KnowledgeBase.load(data_dir))
    writer = ClaudeWriter(model=args.model) if args.llm else None
    cases = [c for c in CASES if not args.case or args.case in c.id]

    results = [evaluate(case, retriever, writer) for case in cases]
    report(results, args.show_answers)
    return 0 if all(r.recall for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
