"""Suggestions around an answer, all derived from the user's own documents.

- starter questions for a chat, built from the user's plans (names, covered
  services, end dates);
- follow-up questions, chosen by which kinds of policy section the answer
  drew on;
- next steps, triggered by specific policy wording in the passages that
  were quoted (prior authorization, referral, visit limits, exclusions).

Next steps are suggestions, not determinations: each one carries the page
and section whose wording triggered it, and none promises coverage.
"""

import re

from ..models.policy import DocumentChunk

MAX_STARTERS = 6
MAX_FOLLOW_UPS = 3
MAX_NEXT_STEPS = 3


def _name(entry: dict) -> str:
    return entry.get("display_name") or entry.get("plan_name") or entry["filename"]


# ── Starter questions ────────────────────────────────────────────────

def starters(entries: list[dict], covered_services: dict[str, list[str]]) -> list[str]:
    """Questions to start with, for the documents in scope.

    `covered_services` maps document_id → service names from its summary.
    """
    if not entries:
        return [
            "What does my plan cover?",
            "What needs prior authorization?",
            "What are my copays and deductible?",
        ]
    out: list[str] = []
    for e in entries[:2]:
        name = _name(e)
        out.append(f"What are my copays and deductible under {name}?")
        out.append(f"What needs prior authorization under {name}?")
        for service in covered_services.get(e["document_id"], [])[:1]:
            out.append(f"Is {service.lower()} covered under {name}?")
        if e.get("expiration_date"):
            out.append(f"When does {name} start and end?")
    if len(entries) > 1:
        out.insert(0, "Which of my plans has the lower deductible?")
    seen, unique = set(), []
    for q in out:
        if q not in seen:
            seen.add(q)
            unique.append(q)
    return unique[:MAX_STARTERS]


# ── Follow-up questions ──────────────────────────────────────────────

_SECTION_FOLLOW_UPS = [
    (("prior auth", "approval", "precertification", "pre-certification"),
     "What does my provider need to submit for prior authorization?"),
    (("exclusion", "not covered", "do not cover", "not cover"),
     "Are there similar services my plan does cover?"),
    (("copay", "cost", "deductible", "you pay", "coinsurance"),
     "What is my out-of-pocket maximum?"),
    (("referral",), "When do I need a referral?"),
    (("appeal", "grievance", "disagree"), "How long do I have to file an appeal?"),
    (("covered", "benefit", "plan cover"), "Are there limits on how often this is covered?"),
]

_DEFAULT_FOLLOW_UPS = [
    "What services need prior authorization under this plan?",
    "What does this plan not cover?",
    "What are my copays?",
]


def follow_ups(question: str, retrieved: list[tuple[DocumentChunk, float]]) -> list[str]:
    """Follow-ups for the kinds of section the answer drew on (best first),
    skipping any that just repeat the question's topic."""
    q = question.lower()
    out: list[str] = []
    for chunk, _ in retrieved:
        heading = chunk.section_heading.lower()
        for keys, suggestion in _SECTION_FOLLOW_UPS:
            if any(k in heading for k in keys) and suggestion not in out:
                if not any(k in q for k in keys):
                    out.append(suggestion)
    for d in _DEFAULT_FOLLOW_UPS:
        if len(out) >= MAX_FOLLOW_UPS:
            break
        # skip defaults on a topic already suggested (e.g. two prior-auth questions)
        if d not in out and not ("prior authorization" in d and any("prior authorization" in o for o in out)):
            out.append(d)
    return out[:MAX_FOLLOW_UPS]


# ── Next steps ───────────────────────────────────────────────────────

_LIMIT_RE = re.compile(r"(?:limited to|up to) \d+ (?:combined )?(?:visits|days)[^.;,]*", re.I)

_RULES = [
    (re.compile(r"prior authori[sz]ation|precertification|advance approval|needs? approval|"
                r"requires? approval|gets? approval", re.I),
     "Ask your provider to request prior authorization before the service; without it, the "
     "policy says the claim may be denied or reduced."),
    (re.compile(r"referral", re.I),
     "Get a referral from your primary care provider before booking."),
]
# Wording that says the opposite of a rule ("does not require referrals")
_NEGATED = {
    "Get a referral from your primary care provider before booking.": re.compile(
        r"\bno referrals?\b|referrals? (?:are|is) not (?:needed|required)|"
        r"(?:does|do) not (?:need|require) (?:a )?referrals?|without a referral", re.I),
}


def next_steps(paragraphs: list[tuple[str, str]], retrieved: list[tuple[DocumentChunk, float]]
               ) -> list[dict]:
    """Next steps triggered by policy wording in the quoted paragraphs.

    `paragraphs` is [(chunk_id, text)] best first: sentences of the quoted
    passages, already narrowed to those about the question's subject. Each
    step records where its trigger appeared.
    """
    by_id = {c.chunk_id: c for c, _ in retrieved}
    steps: list[dict] = []
    used: set[str] = set()

    def add(text: str, chunk: DocumentChunk) -> None:
        if text not in used and len(steps) < MAX_NEXT_STEPS:
            used.add(text)
            steps.append({"text": text, "document_id": chunk.document_id,
                          "page_number": chunk.page_number, "section": chunk.section_heading})

    for chunk_id, text in paragraphs:
        chunk = by_id.get(chunk_id)
        if chunk is None:
            continue
        heading = chunk.section_heading.lower()
        if any(k in heading for k in ("exclusion", "not covered", "do not cover", "not cover")):
            add("This appears under exclusions. Ask your provider about covered alternatives, "
                "and confirm with your insurer before going ahead.", chunk)
            continue
        for pattern, step in _RULES:
            negated = _NEGATED.get(step)
            if negated and negated.search(text):
                continue
            # a bullet under a prior-auth heading counts even without the wording
            if pattern.search(text) or pattern.search(heading):
                add(step, chunk)
        if m := _LIMIT_RE.search(text):
            add(f"Keep track of how much you use: the policy says it is {m.group(0).strip()}.", chunk)
    return steps
