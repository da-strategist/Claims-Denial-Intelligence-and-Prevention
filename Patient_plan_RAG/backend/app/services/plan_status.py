"""Questions about whether a plan is active ("Is this plan still active?",
"When does my coverage end?") are answered from the plan dates the document
states, not from keyword search: policies say "Effective Date" or "Coverage
Period", never "active".

The dates are quoted verbatim with their page and section and compared with
today's date. They describe the plan period only: they cannot show whether
the person is still enrolled, so the answer always says so.
"""

import re
from datetime import date

from ..models.policy import DocumentChunk
from . import suggestions
from .document_processor import find_plan_period

_STATUS = re.compile(
    r"\b(still\s+(?:active|valid|good|on|in\s+(?:effect|force))|active|inactive|expired?|expiring"
    r"|expiry|expiration|lapsed?|in\s+(?:effect|force)|valid|current|renew(?:s|ed|al)?|ended?"
    r"|cancel(?:l?ed)?)\b", re.I)
_SUBJECT = re.compile(r"\b(plan|policy|coverage|insurance|it|this)\b", re.I)
_DATES = re.compile(
    r"\b((?:start|end|renewal|effective|expiration|expiry|termination)\s+date"
    r"|coverage\s+(?:period|dates?)|(?:plan|policy|benefit)\s+(?:year|period|dates?|term)"
    r"|when\s+(?:does|did|will|do)\s+(?:my|the|this|our|her|his|their)\s+"
    r"(?:plan|policy|coverage|insurance)\s+(?:start|begin|end|expire|run\s+out|renew|stop))\b", re.I)
# about something else that can be "valid" or "expire" (an approval, a drug)
_OTHER = re.compile(r"\b(authori[sz]ation|approval|referral|pre-?cert\w*|prescription|"
                    r"card|claim|appeal|deductible|benefit\s+maximum)\b", re.I)


def is_status_question(question: str) -> bool:
    if _OTHER.search(question):
        return False
    return bool(_DATES.search(question) or (_STATUS.search(question) and _SUBJECT.search(question)))


def _long(d: date) -> str:
    return f"{d:%B} {d.day}, {d.year}"


def _source(chunks: list[DocumentChunk]) -> tuple[date | None, date | None, str, DocumentChunk | None]:
    """Plan dates from the first pages of one document, with the chunk that
    holds the (first) line they were read from."""
    first_pages = sorted({c.page_number for c in chunks})[:2]
    text = "\n".join(c.content for c in chunks if c.page_number in first_pages)
    start, end, line = find_plan_period(text)
    if not line:
        return None, None, "", None
    first = line.splitlines()[0]
    chunk = next((c for c in chunks if first in c.content), None)
    return start, end, line, chunk


def _status(start: date | None, end: date | None, today: date) -> str:
    if start and today < start:
        return f"By these dates the plan period has not started yet (it starts on {_long(start)})."
    if end and today > end:
        return f"By these dates the plan period ended on {_long(end)}."
    if start and end:
        return f"By these dates today ({_long(today)}) falls within the plan period."
    if end:
        return f"The document gives an end date of {_long(end)}, which has not passed yet."
    return f"The document gives a start date of {_long(start)} but no end date."


def answer(chunks: list[DocumentChunk], names: dict[str, str], audience: str,
           today: date | None = None) -> dict | None:
    """Status of each plan in scope, or None when no document states its
    dates (the question then goes through the usual search)."""
    today = today or date.today()
    member = audience == suggestions.MEMBER
    by_doc: dict[str, list[DocumentChunk]] = {}
    for c in chunks:
        by_doc.setdefault(c.document_id, []).append(c)

    found, missing = [], []
    for doc_id, doc_chunks in by_doc.items():
        start, end, line, chunk = _source(doc_chunks)
        name = names.get(doc_id) or doc_id
        if chunk is None:
            missing.append(name)
            continue
        found.append({"document_id": doc_id, "name": name, "line": line, "chunk": chunk,
                      "status": _status(start, end, today)})
    if not found:
        return None

    enrolment = (
        "These dates describe the plan period only. They don't show whether you are still "
        "enrolled: coverage can end early (for example unpaid premiums or leaving an "
        "employer's plan) or be renewed. Your insurer can confirm your current coverage."
        if member else
        "These dates describe the plan period only. They don't confirm the patient is still "
        "enrolled: verify current eligibility with the payer.")
    several = len(found) + len(missing) > 1
    statuses = [(f"{f['name']}: " if several else "") + f["status"] for f in found]
    if missing:
        statuses.append("No plan dates were found in: " + ", ".join(missing) + ".")
    lead = "\n".join(statuses) + "\n\n" + enrolment
    quoted = [f"{f['name']} (page {f['chunk'].page_number}): \"{f['line'].replace(chr(10), '; ')}\""
              for f in found]
    return {
        "lead": lead,
        "text": lead + "\n\n" + "\n".join(quoted),
        "quotes": [{"document_id": f["document_id"], "page_number": f["chunk"].page_number,
                    "section": f["chunk"].section_heading, "quote": f["line"],
                    "from_scan": bool(f["chunk"].metadata.get("from_scan"))} for f in found],
        "chunks": [f["chunk"] for f in found],
    }
