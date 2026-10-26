"""How a chat answer is laid out: what the policy says (quotes grouped by
plan), where plans differ, and a fixed "keep in mind" note.

When a question matches several of the user's plans and none is named, each
plan's wording is shown separately and differing amounts are pointed out,
rather than blending plans into one answer.
"""

import re

from ..models.policy import DocumentChunk
from . import suggestions
from .policy_summarizer import summarize_policy
from .retrieval import _tokenize

QUOTES_ONE_PLAN = 2
MAX_PLANS = 3

# Fixed wording, never generated: what an explanation of a policy is not.
KEEP_IN_MIND = {
    suggestions.MEMBER: (
        "This explains your policy document. It is not a coverage decision. A "
        "prior-authorization requirement is not an approval, and an approval does not "
        "guarantee payment. Your current eligibility and your provider's network status "
        "have not been checked: confirm with your insurer."),
    suggestions.STAFF: (
        "This explains the patient's policy document. It is not a coverage decision. A "
        "prior-authorization requirement is not an approval, and an approval does not "
        "guarantee payment. The patient's current eligibility and your network status "
        "have not been checked: verify with the payer."),
}


def select_quotes(scored: list[tuple[float, str, str]],
                  retrieved: list[tuple[DocumentChunk, float]]) -> list[dict]:
    """The passages to show, as dicts with document, page, section and quote.

    One plan: its two best paragraphs. Several plans: the best paragraph of
    each (up to MAX_PLANS), so no plan is crowded out by another.
    """
    by_id = {chunk.chunk_id: chunk for chunk, _ in retrieved}
    picked: list[tuple[DocumentChunk, str]] = []
    docs_in_order: list[str] = []
    for _, chunk_id, text in scored:
        doc = by_id[chunk_id].document_id
        if doc not in docs_in_order:
            docs_in_order.append(doc)
    if len(docs_in_order) <= 1:
        picked = [(by_id[cid], text) for _, cid, text in scored[:QUOTES_ONE_PLAN]]
    else:
        for doc in docs_in_order[:MAX_PLANS]:
            _, cid, text = next(s for s in scored if by_id[s[1]].document_id == doc)
            picked.append((by_id[cid], text))
    return [{"document_id": c.document_id, "page_number": c.page_number,
             "section": c.section_heading or "General", "quote": text,
             "from_scan": bool(c.metadata.get("from_scan"))} for c, text in picked]


# ── Differences between plans ────────────────────────────────────────

_AMOUNT_RE = re.compile(r"\$[\d,]+(?:\.\d+)?|\d+(?:\.\d+)?\s*%")

# (topic, words in the question, summary field, summary source category)
_TOPICS = [
    ("Deductible", ("deductible",), lambda s: s.deductible.get("description", ""), "deductible"),
    ("Out-of-pocket maximum", ("out-of-pocket", "out of pocket", "oop", "maximum"),
     lambda s: s.out_of_pocket_max.get("description", ""), "out_of_pocket_max"),
    ("Coinsurance", ("coinsurance",), lambda s: s.coinsurance.get("description", ""), "coinsurance"),
]


def _source(summary, category: str) -> tuple[int | None, str]:
    ref = next((r for r in summary.source_references if r.get("category") == category), {})
    page = ref.get("page")
    return (int(page) if str(page).isdigit() else None), ref.get("section", "")


def _amounts(text: str) -> set[str]:
    return {re.sub(r"[\s,]", "", a) for a in _AMOUNT_RE.findall(text or "")}


def differences(question: str, document_ids: list[str], chunks_by_doc: dict[str, list],
                names: dict[str, str]) -> list[dict]:
    """Amounts the question is about that differ between the plans shown:
    [{"topic", "values": [{"document_id", "document_name", "value", "page_number",
    "section"}]}]. A plan that doesn't state the amount shows "Not stated"."""
    if len(document_ids) < 2:
        return []
    q = question.lower()
    q_tokens = set(_tokenize(question))
    summaries = {d: summarize_policy(d, chunks_by_doc.get(d, [])) for d in document_ids}

    fields: list[tuple[str, dict[str, str], str]] = []
    for topic, words, get, category in _TOPICS:
        if any(w in q for w in words):
            fields.append((topic, {d: get(s) for d, s in summaries.items()}, category))
    # copays for a service the question names ("specialist", "urgent care", ...)
    services: dict[str, dict[str, str]] = {}
    for d, s in summaries.items():
        for row in s.copayments:
            service = row.get("service", "")
            tokens = set(_tokenize(service))
            if service and service != "Note" and tokens and tokens <= q_tokens | {"visit", "office"} \
                    and tokens & q_tokens:
                services.setdefault(service, {})[d] = row.get("amount", "")
    fields += [(service, values, "copayments") for service, values in sorted(services.items())]

    out = []
    for topic, values, category in fields:
        amounts = [frozenset(_amounts(values.get(d, ""))) for d in document_ids]
        if len(set(amounts)) > 1:
            rows = []
            for d in document_ids:
                page, section = _source(summaries[d], category) if values.get(d) else (None, "")
                rows.append({"document_id": d, "document_name": names.get(d, d),
                             "value": values.get(d) or "Not stated",
                             "page_number": page, "section": section})
            out.append({"topic": topic, "values": rows})
    return out


def quotes_for_differences(quotes: list[dict], diffs: list[dict]) -> list[dict]:
    """When plans differ, show each plan's own wording of the first differing
    amount (verbatim from its summary, with page and section) instead of
    whatever paragraph ranked best for that plan."""
    if not diffs:
        return quotes
    stated = {v["document_id"]: v for v in diffs[0]["values"] if v["value"] != "Not stated"}
    out = []
    for q in quotes:
        v = stated.get(q["document_id"])
        out.append({**q, "quote": v["value"], "page_number": v["page_number"] or q["page_number"],
                    "section": v["section"] or q["section"], "from_scan": q["from_scan"]}
                   if v else q)
    return out


def lead(question: str, plan_count: int, audience: str) -> str:
    """One line introducing the answer."""
    whose = "your" if audience == suggestions.MEMBER else "the patient's"
    if plan_count > 1:
        return (f"Your question matches {plan_count} of {whose} plans, so each is shown "
                f"separately. Name a plan in your question to see only that one.")
    q = question.lower()
    topic = next((label for label, words in (
        ("prior authorization", ("prior auth", "pre-cert", "precertification", "authorization",
                                 "approval")),
        ("costs", ("cost", "copay", "deductible", "coinsurance", "out of pocket", "pay")),
        ("coverage", ("cover", "included", "eligible", "benefit")),
    ) if any(w in q for w in words)), None)
    return f"Here is what {whose} policy says" + (f" about {topic}." if topic else ".")
