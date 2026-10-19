"""Generate structured policy summaries from chunks.

Chunks are grouped back into their sections (by section_heading), each summary
field is filled from the section whose heading names it, and section text is
split into items: "LABEL: text" paragraphs and "•" bullets. All text is copied
verbatim from the policy; nothing is paraphrased or inferred.
"""

import re
from dataclasses import dataclass, field

from ..models.policy import DocumentChunk, PolicySummary

# Lines at least this long are treated as soft-wrapped by the PDF, so the next
# line continues the same paragraph.
_WRAP_WIDTH = 75

_LABEL_RE = re.compile(r"^([A-Z][A-Za-z0-9 ()/&,'-]{1,60}):\s+(.+)$", re.S)


@dataclass
class _Section:
    heading: str
    page: int | None
    lines: list[str] = field(default_factory=list)

    @property
    def body(self) -> list[str]:
        """Lines without the leading heading line(s)."""
        lines = list(self.lines)
        while lines and lines[0].isupper() and ":" not in lines[0]:
            lines.pop(0)
        return lines


def _group_sections(chunks: list[DocumentChunk]) -> list[_Section]:
    """Merge consecutive chunks of the same section, dropping overlap lines."""
    sections: list[_Section] = []
    for chunk in chunks:
        lines = [ln for ln in chunk.content.split("\n") if ln.strip()]
        if sections and sections[-1].heading == chunk.section_heading:
            acc = sections[-1].lines
            # drop the longest prefix of this chunk that repeats acc's tail
            for k in range(min(len(acc), len(lines)), 0, -1):
                if acc[-k:] == lines[:k]:
                    lines = lines[k:]
                    break
            acc.extend(lines)
        else:
            sections.append(_Section(chunk.section_heading, chunk.page_number, lines))
    return sections


def _find_section(sections: list[_Section], *keywords: str) -> _Section | None:
    """First section whose heading contains a keyword, else whose text does."""
    for sec in sections:
        if any(kw in sec.heading.lower() for kw in keywords):
            return sec
    for sec in sections:
        text = "\n".join(sec.lines).lower()
        if any(kw in text for kw in keywords):
            return sec
    return None


def _paragraphs(lines: list[str]) -> list[str]:
    """Re-join PDF soft-wrapped lines into paragraphs."""
    paras: list[str] = []
    for line in lines:
        starts_new = line.startswith("•") or bool(_LABEL_RE.match(line))
        if paras and not starts_new and len(prev_line) >= _WRAP_WIDTH:
            paras[-1] += " " + line
        else:
            paras.append(line)
        prev_line = line
    return paras


def _labelled(paras: list[str]) -> list[tuple[str, str]]:
    """(label, text) for paragraphs shaped like 'LABEL: text'."""
    items = []
    for p in paras:
        m = _LABEL_RE.match(p)
        if m:
            items.append((m.group(1).strip(), m.group(2).strip()))
    return items


def _bullets(paras: list[str]) -> list[str]:
    return [p.lstrip("• ").strip() for p in paras if p.startswith("•")]


def _split_parenthetical(text: str) -> tuple[str, str]:
    """'Dental services (covered under separate dental plan)' → name, note."""
    m = re.match(r"^(.*?)\s*\((.*)\)\s*$", text)
    if m and m.group(1):
        return m.group(1), m.group(2)
    return text, ""


def _joined(section: _Section) -> str:
    return "; ".join(_paragraphs(section.body))


def summarize_policy(
    document_id: str,
    chunks: list[DocumentChunk],
) -> PolicySummary:
    """Build a structured summary from a policy's chunks."""
    summary = PolicySummary(document_id=document_id)
    if not chunks:
        return summary

    sections = _group_sections(chunks)

    def cite(category: str, sec: _Section) -> None:
        summary.source_references.append(
            {"category": category, "page": sec.page, "section": sec.heading}
        )

    # Plan overview
    overview = _find_section(sections, "overview", "summary of benefits")
    if overview:
        summary.plan_overview = "\n".join(_paragraphs(overview.body))[:800]
        cite("plan_overview", overview)
    else:
        summary.plan_overview = chunks[0].content[:500]

    # Deductible / coinsurance / out-of-pocket maximum
    for attr, category, keywords in [
        ("deductible", "deductible", ("deductible",)),
        ("coinsurance", "coinsurance", ("coinsurance", "co-insurance")),
        ("out_of_pocket_max", "out_of_pocket_max", ("out-of-pocket", "out of pocket")),
    ]:
        sec = _find_section(sections, *keywords)
        if sec:
            value = {"description": _joined(sec)}
            if attr == "deductible":
                value["page"] = str(sec.page or "")
            setattr(summary, attr, value)
            cite(category, sec)

    # Copayments: one row per "Service: amount" line
    sec = _find_section(sections, "copay", "co-pay")
    if sec:
        paras = _paragraphs(sec.body)
        summary.copayments = [
            {"service": label, "amount": text} for label, text in _labelled(paras)
        ]
        # unlabelled notes after the table (e.g. out-of-network rules)
        notes = [p for p in paras[1:] if not _LABEL_RE.match(p)]
        summary.copayments += [{"service": "Note", "amount": n} for n in notes]
        cite("copayments", sec)

    # Covered services: one row per "SERVICE: description" paragraph
    sec = _find_section(sections, "covered services", "benefits")
    if sec:
        for label, text in _labelled(_paragraphs(sec.body)):
            summary.covered_services.append({"service": label, "description": text})
            for sentence in re.split(r"(?<=\.)\s+", text):
                if "limited to" in sentence.lower():
                    summary.important_limitations.append(f"{label}: {sentence}")
        cite("covered_services", sec)

    # Exclusions: one row per bullet
    sec = _find_section(sections, "exclusion", "not covered")
    if sec:
        for bullet in _bullets(_paragraphs(sec.body)):
            name, note = _split_parenthetical(bullet)
            summary.excluded_services.append(
                {"service": name, "description": note or "Not covered"}
            )
        cite("excluded_services", sec)

    # Prior authorization: one row per bullet
    sec = _find_section(sections, "prior auth", "precertification", "pre-certification")
    if sec:
        for bullet in _bullets(_paragraphs(sec.body)):
            summary.prior_auth_services.append(
                {"service": bullet, "requirement": "Prior authorization required"}
            )
        cite("prior_auth_services", sec)

    # Network provisions and referral rules
    sec = _find_section(sections, "network")
    if sec:
        items = _labelled(_paragraphs(sec.body))
        network = [f"{label}: {text}" for label, text in items if "network" in label.lower()]
        summary.network_provisions = {"description": " ".join(network) or _joined(sec)}
        cite("network_provisions", sec)
    for sec in sections:
        referral = [
            text for label, text in _labelled(_paragraphs(sec.body))
            if "referral" in label.lower()
        ]
        if referral:
            summary.referral_requirements = referral[0]
            cite("referral_requirements", sec)
            break

    return summary
