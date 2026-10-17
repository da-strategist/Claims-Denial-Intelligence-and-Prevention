"""Clarification assistant: retrieve reference records for a question, then answer with citations.

Retrieval is deterministic. The claim's codes (CPT, ICD-10, payer, CARC/RARC) and any codes
named in the question look up the sources that govern them exactly; keyword (BM25) scoring
over the source text covers free-typed questions. Claude then writes the answer from those
sources only, citing them as [S1], [S2]. Without an API key the assistant still returns the
sources with a templated summary.

Only `ClaimFacts` (codes and amounts) and the question, with identifiers, dates, and people's
names masked, are sent to Claude.
"""

import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from app.data.knowledge import KnowledgeBase, Source, get_knowledge_base
from app.data.repository import get_repository
from app.models import (
    AssistantAnswer,
    AssistantMode,
    AssistantSource,
    ClaimDetail,
    ClaimFacts,
    ClaimLineFacts,
    ClarificationTopic,
    DenialFacts,
    SourceType,
)

DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_SOURCES = 8

# Source types each topic is mostly answered from
TOPIC_SOURCES: dict[ClarificationTopic, set[SourceType]] = {
    ClarificationTopic.MEDICAL_NECESSITY: {SourceType.COVERAGE_POLICY},
    ClarificationTopic.NCCI_MODIFIERS: {SourceType.NCCI_EDIT, SourceType.MUE},
    ClarificationTopic.PAYER_PRIOR_AUTH: {SourceType.PAYER, SourceType.PAYER_CONTRACT},
    ClarificationTopic.APPEAL: {SourceType.CARC, SourceType.RARC},
}
TOPIC_BOOST = 1.5
PAYER_SCOPED = {SourceType.PAYER, SourceType.PAYER_CONTRACT}


# --- What may be shared ---------------------------------------------------------------


def claim_facts(claim: ClaimDetail) -> ClaimFacts:
    """The codes-and-amounts view of a claim; see ClaimFacts for what's left out."""
    return ClaimFacts(
        claim_type=claim.claim_type,
        place_of_service=claim.place_of_service,
        service_year=claim.service_date.year,
        status=claim.status,
        payer_id=claim.payer_id,
        payer_name=claim.payer.payer_name if claim.payer else None,
        payer_type=claim.payer.payer_type if claim.payer else None,
        other_payer_ids=claim.other_payer_ids,
        primary_icd10=claim.primary_icd10,
        additional_icd10=claim.additional_icd10,
        lines=[
            ClaimLineFacts(
                cpt_code=line.cpt_code,
                cpt_category=line.cpt_category,
                modifier=line.modifier,
                units=line.units,
                charge_amount=line.charge_amount,
                icd10_pointer=line.icd10_pointer,
            )
            for line in claim.lines
        ],
        total_charge=claim.total_charge,
        total_paid=claim.total_paid,
        days_in_ar=claim.days_in_ar,
        pa_required=claim.pa_required,
        pa_obtained=claim.pa_obtained,
        has_pa_number=bool(claim.pa_number),
        denials=[
            DenialFacts(
                carc_code=denial.carc_code,
                rarc_code=denial.rarc_code,
                root_cause_category=denial.root_cause_category,
                denial_amount=denial.denial_amount,
                is_preventable=denial.is_preventable,
            )
            for denial in claim.denials
        ],
    )


# Identifiers a specialist might paste into a question; replaced before anything is sent
_IDENTIFIERS = [
    (re.compile(r"\bPAT\d{6}\b", re.I), "[patient]"),
    (re.compile(r"\bCLM\d{7}\b", re.I), "[claim]"),
    (re.compile(r"\bPROV\d{3}\b", re.I), "[provider]"),
    (re.compile(r"\b\d{10}\b"), "[number]"),  # NPI, phone, member numbers
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b"), "[date]"),
]


_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")
_TITLE = re.compile(r"^(?:mr|mrs|ms|miss|mx|dr)\.?$", re.I)
# Words that introduce a person, so a known surname after them is a name ("patient Garcia")
_PERSON_CUES = frozenset("patient pt member subscriber provider doctor physician".split())


class NameScrubber:
    """Masks people's names in a question before it's sent anywhere.

    Catches the registered patients' and providers' names ("Karen Sanchez", "Sanchez, Karen"),
    a known surname after a title or a word like "patient" ("Mrs. Sanchez", "patient
    Sanchez's"), and any capitalised word after a title ("Dr. Whoever"). A first name or
    surname on its own is left alone: too many are ordinary words ("Will", "Price", "Long").
    """

    def __init__(self, names: list[tuple[str, str]] = ()) -> None:
        self.full_names = {f"{first} {last}".lower() for first, last in names}
        self.surnames = {last.lower() for _, last in names}

    def _full_name(self, text: str, words: list[re.Match], i: int) -> int:
        """2 if words i and i+1 are a known "First Last" or "Last, First", else 0."""
        if i + 1 >= len(words):
            return 0
        a, b = words[i], words[i + 1]
        gap = text[a.end() : b.start()].strip()
        first, second = _bare(a), _bare(b)
        if gap == "" and f"{first} {second}" in self.full_names:
            return 2
        if gap == "," and f"{second} {first}" in self.full_names:
            return 2
        return 0

    def scrub(self, text: str) -> str:
        words = list(_WORD.finditer(text))
        spans, i = [], 0
        while i < len(words):
            word = words[i]
            if n := self._full_name(text, words, i):
                spans.append((word.start(), words[i + n - 1].end()))
                i += n
                continue
            nxt = words[i + 1] if i + 1 < len(words) else None
            if nxt and nxt.group()[0].isupper() and not text[word.end() : nxt.start()].strip(" ."):
                title = bool(_TITLE.match(word.group()))
                if title or (word.group().lower() in _PERSON_CUES and _bare(nxt) in self.surnames):
                    n = self._full_name(text, words, i + 1) or 1  # "Dr. Carol Robinson"
                    spans.append((word.start() if title else nxt.start(), words[i + n].end()))
                    i += 1 + n
                    continue
            i += 1
        for start, end in reversed(spans):
            possessive = "'s" if text[start:end].endswith("'s") else ""
            text = f"{text[:start]}[name]{possessive}{text[end:]}"
        return text


def _bare(word: re.Match) -> str:
    return word.group().removesuffix("'s").lower()


def scrub_question(question: str, names: NameScrubber | None = None) -> str:
    """The question with identifiers, dates, and people's names masked."""
    for pattern, replacement in _IDENTIFIERS:
        question = pattern.sub(replacement, question)
    return (names or NameScrubber()).scrub(question).strip()


# --- Retrieval ------------------------------------------------------------------------

_TOKEN = re.compile(r"[a-z0-9]+(?:\.[a-z0-9]+)?")
_STOPWORDS = frozenset(
    "a an and are as at be by can do does for from how i if in is it its my of on or "
    "should that the this to was we what when which why will with this claim".split()
)


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS]


class _Bm25:
    """Okapi BM25 over the source texts, for free-typed questions."""

    def __init__(self, texts: list[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.docs = [Counter(_tokens(text)) for text in texts]
        self.lengths = [sum(doc.values()) for doc in self.docs]
        self.avg_length = sum(self.lengths) / max(len(self.docs), 1)
        frequency = Counter(token for doc in self.docs for token in doc)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in frequency.items()}
        self.k1, self.b = k1, b

    def scores(self, query: str) -> list[float]:
        terms = set(_tokens(query))
        results = []
        for doc, length in zip(self.docs, self.lengths):
            score = 0.0
            for term in terms & doc.keys():
                tf = doc[term]
                norm = tf + self.k1 * (1 - self.b + self.b * length / self.avg_length)
                score += self.idf[term] * tf * (self.k1 + 1) / norm
            results.append(score)
        return results


_CPT = re.compile(r"\b(\d{5}|G\d{4})\b")
_ICD10 = re.compile(r"\b([A-TV-Z]\d{2}(?:\.[A-Z0-9]{1,4})?)\b")
_CARC = re.compile(r"\b(?:CARC|CO|PR|OA|PI)[\s-]*(\d{1,3})\b", re.I)
_RARC = re.compile(r"\b(MA\d{2,3}|N\d{1,3}|M\d{1,3})\b")
_PAYER = re.compile(r"\b(PAY\d{3})\b")


def _question_keys(question: str, payer_names: dict[str, str]) -> set[str]:
    keys = {f"cpt:{c}" for c in _CPT.findall(question)}
    keys |= {f"icd10:{c}" for c in _ICD10.findall(question.upper())}
    keys |= {f"carc:{c}" for c in _CARC.findall(question)}
    keys |= {f"rarc:{c}" for c in _RARC.findall(question.upper())}
    keys |= {f"payer:{p}" for p in _PAYER.findall(question.upper())}
    lowered = question.lower()
    keys |= {f"payer:{pid}" for pid, name in payer_names.items() if name.lower() in lowered}
    return keys


@dataclass
class Match:
    source: Source
    score: float
    reason: str


def _claim_match(source: Source, facts: ClaimFacts) -> tuple[float, str] | None:
    """How strongly a source applies to the claim's own codes, and why."""
    cpts = {line.cpt_code for line in facts.lines}
    diagnoses = [facts.primary_icd10, *facts.additional_icd10]
    data = source.data
    match source.source_type:
        case SourceType.COVERAGE_POLICY:
            billed = [c for c in data["cpt_list"] if c in cpts]
            if not billed:
                return None
            covered = [d for d in diagnoses if d in data["icd10_list"]]
            procedures = f"Covers billed CPT {', '.join(billed)}"
            if covered:
                listed = ", ".join(covered)
                return 3.0, f"{procedures}; claim diagnosis {listed} is on its covered list"
            # An uncovered diagnosis is the likelier denial, so rank it a little higher
            return 3.5, (
                f"{procedures}; none of the claim's diagnoses ({', '.join(diagnoses)}) "
                "are on its covered list"
            )
        case SourceType.NCCI_EDIT:
            col1, col2 = data["column_1_cpt"], data["column_2_cpt"]
            if col1 in cpts and col2 in cpts:
                return 4.0, f"The claim bills both CPT {col1} and {col2}"
            if col1 in cpts or col2 in cpts:
                return 1.0, f"The claim bills CPT {col1 if col1 in cpts else col2}"
            return None
        case SourceType.MUE:
            units = sum(line.units for line in facts.lines if line.cpt_code == data["cpt_code"])
            if not units:
                return None
            cpt, limit = data["cpt_code"], int(data["max_units_per_day"])
            if units > limit:
                return 4.0, f"The claim bills {units} units of CPT {cpt}; the limit is {limit}"
            return 1.5, f"The claim bills {units} unit(s) of CPT {cpt} (limit {limit})"
        case SourceType.PAYER:
            if source.reference_id == facts.payer_id:
                return 2.0, "The claim's billed payer"
            if source.reference_id in facts.other_payer_ids:
                return 1.0, "Other coverage on the claim"
            return None
        case SourceType.PAYER_CONTRACT:
            categories = {line.cpt_category for line in facts.lines}
            if data["payer_id"] == facts.payer_id and data["cpt_category"] in categories:
                weight = 2.5 if data["status"] == "Active" else 1.0
                return weight, f"Billed payer's contract for {data['cpt_category']} services"
            return None
        case SourceType.CARC | SourceType.RARC:
            field = "carc_code" if source.source_type == SourceType.CARC else "rarc_code"
            if any(getattr(d, field) == source.reference_id for d in facts.denials):
                return 4.0, "On the claim's denial"
            return None
        case SourceType.FEE_SCHEDULE:
            if source.reference_id in cpts:
                return 1.0, f"Medicare rate for billed CPT {source.reference_id}"
            return None
    return None


def _named_match(source: Source, asked: set[str], question: str) -> tuple[float, str] | None:
    """How strongly a source matches codes, payers, or services named in the question."""
    named = sorted(asked & source.keys)
    if not named:
        return None
    codes = ", ".join(key.split(":", 1)[1] for key in named)
    if source.source_type == SourceType.PAYER_CONTRACT:
        # A payer has a contract per service category; only the category asked about counts
        category = source.data["cpt_category"]
        if category.lower() in question.lower():
            return 3.0, f"Named in the question: {codes}, {category}"
        return 0.5, f"Contract of {codes}, named in the question"
    return 3.0, f"Named in the question: {codes}"


class Retriever:
    def __init__(self, knowledge: KnowledgeBase) -> None:
        self.knowledge = knowledge
        self.bm25 = _Bm25([f"{s.title} {s.text}" for s in knowledge.sources])

    def retrieve(
        self,
        question: str,
        facts: ClaimFacts | None = None,
        topic: ClarificationTopic | None = None,
        limit: int = MAX_SOURCES,
    ) -> list[Match]:
        asked = _question_keys(question, self.knowledge.payer_names)
        keyword = self.bm25.scores(question)
        top_keyword = max(keyword, default=0) or 1.0
        boosted = TOPIC_SOURCES.get(topic, set())

        matches = []
        for source, keyword_score in zip(self.knowledge.sources, keyword):
            score, reasons = 0.0, []
            if facts and (claim := _claim_match(source, facts)):
                score += claim[0]
                reasons.append(claim[1])
            if named := _named_match(source, asked, question):
                score += named[0]
                reasons.append(named[1])
            relative = keyword_score / top_keyword
            # Payer records apply only to their own payer, so wording alone never brings one in
            payer_scoped = source.source_type in PAYER_SCOPED
            if relative >= 0.4 and not (payer_scoped and not reasons):  # weaker overlap is noise
                score += 2.0 * relative
                if not reasons:
                    reasons.append("Matches the question's wording")
            if score and source.source_type in boosted:
                score *= TOPIC_BOOST
            if score:
                matches.append(Match(source, score, "; ".join(reasons)))
        matches.sort(key=lambda m: -m.score)  # stable: ties keep knowledge-base order
        return matches[:limit]


# --- Answer writers -------------------------------------------------------------------


class AssistantUnavailable(Exception):
    """The LLM couldn't answer (network, auth, rate limit); fall back to retrieval."""


class AnswerWriter(Protocol):
    mode: AssistantMode
    model: str | None

    def write(
        self, question: str, facts: ClaimFacts | None, sources: list[AssistantSource]
    ) -> str: ...


SYSTEM_PROMPT = """\
You are a clarification assistant for hospital billing specialists working claim denials \
and pre-submission edits.

Answer using ONLY the numbered reference sources provided. They come from the organization's \
reference tables: CARC/RARC codes, NCCI procedure-to-procedure edits, MUE limits, LCD/NCD \
coverage policies, payer profiles and contracts, and the Medicare fee schedule.

- Cite every factual statement with its source label in square brackets, e.g. [S1] or [S1][S3].
- Apply the sources to the claim facts when they are given: say which codes on this claim \
a source affects and how.
- If the sources don't answer the question, say so plainly and name what would be needed \
(for example the payer's prior authorization list or the clinical documentation). Never \
guess, and never invent codes, policies, payment amounts, or deadlines.
- Start with a direct answer in one or two sentences, then short bullet points, then next \
steps for the specialist.
- When asked for appeal wording, draft a short appeal paragraph grounded in the cited codes \
and policies, with placeholders such as [date of service] for details you don't have.
- Keep it under 250 words unless drafting an appeal."""


def build_prompt(question: str, facts: ClaimFacts | None, sources: list[AssistantSource]) -> str:
    """The user message sent to Claude: claim facts, numbered sources, then the question."""
    parts = []
    if facts:
        parts.append(f"<claim_facts>\n{facts.model_dump_json(indent=1)}\n</claim_facts>")
    listed = "\n\n".join(
        f"[{s.label}] {s.title} ({s.source_type} {s.reference_id})\n{s.excerpt}" for s in sources
    )
    parts.append(f"<sources>\n{listed}\n</sources>")
    parts.append(f"<question>\n{question}\n</question>")
    return "\n\n".join(parts)


def _api_error_message(err: Exception) -> str:
    """Anthropic's own message (e.g. "Your credit balance is too low…"), not the raw JSON."""
    body = getattr(err, "body", None)
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        return body["error"].get("message") or str(err)
    return getattr(err, "message", None) or str(err)


class ClaudeWriter:
    mode = AssistantMode.CLAUDE

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None) -> None:
        import anthropic  # imported here so retrieval-only installs never need it

        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key, max_retries=2, timeout=60)
        self._errors = (anthropic.APIError,)

    def write(
        self, question: str, facts: ClaimFacts | None, sources: list[AssistantSource]
    ) -> str:
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=1500,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": build_prompt(question, facts, sources)}],
            )
        except self._errors as err:
            raise AssistantUnavailable(_api_error_message(err)) from err
        return "".join(block.text for block in response.content if block.type == "text").strip()


class RetrievalWriter:
    """No LLM: list the retrieved sources, most relevant first, each cited."""

    mode = AssistantMode.RETRIEVAL
    model = None

    def write(
        self, question: str, facts: ClaimFacts | None, sources: list[AssistantSource]
    ) -> str:
        lines = ["The most relevant reference records, most relevant first:"]
        lines += [f"- {s.title}. {s.match_reason}. [{s.label}]" for s in sources]
        return "\n".join(lines)


NO_SOURCES = (
    "No reference record matches this question. The knowledge base holds CARC/RARC codes, "
    "NCCI edits, MUE limits, LCD/NCD coverage policies, payer profiles and contracts, and the "
    "Medicare fee schedule; try naming a code, procedure, or payer."
)

_CITATION = re.compile(r"\[(S\d+(?:\s*[,;]\s*S\d+)*)\]")


def cited_labels(answer: str) -> set[str]:
    groups = _CITATION.findall(answer)
    return {label.strip() for group in groups for label in re.split(r"[,;]", group)}


def answer_question(
    question: str,
    facts: ClaimFacts | None,
    topic: ClarificationTopic | None,
    retriever: Retriever,
    writer: AnswerWriter,
    names: NameScrubber | None = None,
) -> AssistantAnswer:
    question = scrub_question(question, names)
    matches = retriever.retrieve(question, facts, topic)
    sources = [
        AssistantSource(
            label=f"S{i}",
            source_type=m.source.source_type,
            reference_id=m.source.reference_id,
            title=m.source.title,
            excerpt=m.source.text,
            match_reason=m.reason,
            cited=False,
        )
        for i, m in enumerate(matches, start=1)
    ]
    mode, model, notice = writer.mode, writer.model, None

    if not sources:
        answer = NO_SOURCES
    else:
        try:
            answer = writer.write(question, facts, sources)
        except AssistantUnavailable as err:
            answer = RetrievalWriter().write(question, facts, sources)
            mode, model = AssistantMode.RETRIEVAL, None
            notice = f"Claude couldn't be reached ({err}), so these are the matching sources."
        if mode == AssistantMode.RETRIEVAL and notice is None:
            notice = "Claude isn't configured (no ANTHROPIC_API_KEY); showing the matching sources."

    cited = cited_labels(answer)
    sources = [s.model_copy(update={"cited": s.label in cited}) for s in sources]
    return AssistantAnswer(
        question=question,
        answer=answer,
        sources=sources,
        mode=mode,
        model=model,
        notice=notice,
        topic=topic,
        claim_facts=facts,
    )


# --- Dependencies ---------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_name_scrubber() -> NameScrubber:
    """Knows the registered patients' and providers' names."""
    return NameScrubber(get_repository().person_names())


@lru_cache(maxsize=1)
def get_retriever() -> Retriever:
    return Retriever(get_knowledge_base())


@lru_cache(maxsize=1)
def get_answer_writer() -> AnswerWriter:
    """Claude when ANTHROPIC_API_KEY is set, unless RCM_ASSISTANT_MODE=retrieval."""
    use_claude = os.environ.get("RCM_ASSISTANT_MODE") != "retrieval"
    if use_claude and os.environ.get("ANTHROPIC_API_KEY"):
        return ClaudeWriter(model=os.environ.get("RCM_ASSISTANT_MODEL", DEFAULT_MODEL))
    return RetrievalWriter()
