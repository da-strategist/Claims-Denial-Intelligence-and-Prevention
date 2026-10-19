"""RAG answer generation with citation grounding.

In demo mode, answers are generated from retrieved context using
template-based logic (no LLM call). In live mode, the Anthropic API
is called with the retrieved passages as context.
"""

import os
import re
from pathlib import Path

from ..models.coverage import ChatResponse, SourceCitation
from ..models.policy import DocumentChunk
from .conversations import Turn
from .retrieval import retrieve_for_policy


# ── Demo answer templates ─────────────────────────────────────────────

_TEMPLATES = {
    "coverage": (
        "Based on the policy evidence retrieved, {service} appears to be "
        "{classification}. {details}\n\n"
        "⚠️ This is an AI-generated interpretation of policy language, not a "
        "coverage determination. Confirm with your insurer before relying on "
        "this assessment."
    ),
    "general": (
        "According to the policy document, {answer}\n\n"
        "⚠️ This interpretation is based on the specific passages cited below. "
        "Policy language may contain additional conditions or exceptions not "
        "captured here. Verify with the plan administrator."
    ),
    "no_evidence": (
        "I could not find sufficient evidence in the uploaded policy "
        "document(s) to answer this question. The policy may not address this "
        "topic, or the relevant section might use different terminology.\n\n"
        "Suggested next steps:\n"
        "• Try rephrasing the question with terms commonly used in insurance "
        "policies\n"
        "• Check the plan's Summary of Benefits and Coverage (SBC)\n"
        "• Contact the plan administrator directly"
    ),
}


def _build_demo_answer(
    question: str,
    retrieved: list[tuple[DocumentChunk, float]],
) -> tuple[str, list[SourceCitation]]:
    """Build a grounded answer from retrieved chunks without an LLM."""
    if not retrieved:
        return _TEMPLATES["no_evidence"], []

    citations: list[SourceCitation] = []
    context_lines: list[str] = []

    for chunk, score in retrieved:
        citations.append(SourceCitation(
            document_id=chunk.document_id,
            page_number=chunk.page_number,
            section=chunk.section_heading,
            excerpt=chunk.content[:300],
            confidence="supported" if score > 0.3 else "interpreted",
        ))
        context_lines.append(chunk.content[:400])

    combined_context = " ... ".join(context_lines)

    # Very simple classification from the question
    q_lower = question.lower()
    if any(kw in q_lower for kw in ["cover", "included", "eligible", "benefit"]):
        answer = _TEMPLATES["general"].format(
            answer=f"the following policy language is relevant to your "
                   f"question about coverage:\n\n\"{combined_context[:500]}...\""
        )
    elif any(kw in q_lower for kw in ["cost", "copay", "deductible", "coinsurance",
                                       "out of pocket", "premium"]):
        answer = _TEMPLATES["general"].format(
            answer=f"the following cost-sharing provisions were found:\n\n"
                   f"\"{combined_context[:500]}...\""
        )
    elif any(kw in q_lower for kw in ["prior auth", "pre-cert", "precertification",
                                       "authorization"]):
        answer = _TEMPLATES["general"].format(
            answer=f"the following prior authorization provisions were found:\n\n"
                   f"\"{combined_context[:500]}...\""
        )
    else:
        answer = _TEMPLATES["general"].format(
            answer=f"the following relevant passages were found:\n\n"
                   f"\"{combined_context[:500]}...\""
        )

    return answer, citations


# ── Live LLM answer ──────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a health insurance policy assistant. You answer 
questions about insurance coverage based ONLY on the policy passages provided. 
Follow these rules strictly:

1. Base every claim on a specific passage. Cite the page number and section.
2. If the passages do not contain enough information, say so clearly.
3. Never fabricate quotes, page numbers, or coverage determinations.
4. Always include this disclaimer: "This is an AI-generated interpretation, 
   not a coverage determination. Verify with your plan administrator."
5. Distinguish between what the policy explicitly states and your interpretation.
6. Use plain language — avoid jargon unless quoting the policy directly.
"""


async def _build_live_answer(
    question: str,
    retrieved: list[tuple[DocumentChunk, float]],
    history: list[Turn] | None = None,
) -> tuple[str, list[SourceCitation]]:
    """Call Anthropic API with retrieved context."""
    import anthropic

    citations: list[SourceCitation] = []
    passages: list[str] = []

    for chunk, score in retrieved:
        label = f"[Page {chunk.page_number or '?'}, {chunk.section_heading or 'General'}]"
        passages.append(f"{label}\n{chunk.content}")
        citations.append(SourceCitation(
            document_id=chunk.document_id,
            page_number=chunk.page_number,
            section=chunk.section_heading,
            excerpt=chunk.content[:300],
            confidence="supported" if score > 0.3 else "interpreted",
        ))

    context_block = "\n\n---\n\n".join(passages)
    user_msg = (
        f"Policy passages:\n\n{context_block}\n\n---\n\n"
        f"Question: {question}"
    )

    client = anthropic.AsyncAnthropic()
    resp = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[
            *(m for t in history or [] for m in (
                {"role": "user", "content": t.question},
                {"role": "assistant", "content": t.answer},
            )),
            {"role": "user", "content": user_msg},
        ],
    )
    answer_text = resp.content[0].text
    return answer_text, citations


# ── Public interface ─────────────────────────────────────────────────

# Words that point back to an earlier subject ("Does it need approval?")
_REFERRING = re.compile(r"\b(it|its|that|this|these|those|they|them|the same)\b", re.I)


def retrieval_query(question: str, history: list[Turn] | None) -> str:
    """Add the previous question to follow-ups that refer back to it.

    Questions that name their own subject ("What about acupuncture?") are
    searched as-is, so the earlier topic cannot crowd them out.
    """
    if history and _REFERRING.search(question):
        return f"{history[-1].question} {question}"
    return question


async def answer_question(
    question: str,
    chunk_dir: Path,
    document_id: str | None = None,
    top_k: int = 5,
    mode: str | None = None,
    history: list[Turn] | None = None,
) -> ChatResponse:
    """Retrieve context and generate a grounded answer.

    `history` holds earlier turns of the same conversation (oldest first).
    The caller owns conversation state and fills in `conversation_id`.
    """
    effective_mode = mode or os.getenv("APP_MODE", "demo")
    query = retrieval_query(question, history)
    retrieved = retrieve_for_policy(query, chunk_dir, document_id, top_k)

    if effective_mode == "live" and os.getenv("ANTHROPIC_API_KEY"):
        answer_text, citations = await _build_live_answer(question, retrieved, history)
    else:
        answer_text, citations = _build_demo_answer(question, retrieved)

    # Suggest follow-up questions
    follow_ups: list[str] = []
    q_lower = question.lower()
    if "cover" in q_lower:
        follow_ups.append("What are the cost-sharing requirements for this service?")
        follow_ups.append("Does this service require prior authorization?")
    if "auth" in q_lower or "prior" in q_lower:
        follow_ups.append("What documentation is needed for this authorization request?")
    if "cost" in q_lower or "pay" in q_lower:
        follow_ups.append("What is the out-of-pocket maximum for this plan?")
    if not follow_ups:
        follow_ups = [
            "What services require prior authorization under this plan?",
            "What are the plan's exclusions and limitations?",
        ]

    return ChatResponse(
        answer=answer_text,
        citations=citations,
        follow_up_suggestions=follow_ups[:3],
        confidence="supported" if retrieved else "insufficient_evidence",
    )
