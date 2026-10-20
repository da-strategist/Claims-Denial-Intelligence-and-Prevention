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
    """Section whose heading contains a keyword, trying keywords in order."""
    for kw in keywords:
        for sec in sections:
            if kw in sec.heading.lower():
                return sec
    return None


def _find_paragraph(sections: list[_Section], *keywords: str) -> tuple[_Section, str] | None:
    """Fallback when no heading names a field: the labelled line whose label
    has a keyword ("Deductible: $7,000 ..."), else the first paragraph that
    mentions one. Keywords are tried in order."""
    for kw in keywords:
        for sec in sections:
            for label, text in _labelled(_paragraphs(sec.body)):
                if kw in label.lower():
                    return sec, f"{label}: {text}"
    for kw in keywords:
        for sec in sections:
            for para in _paragraphs(sec.body):
                if kw in para.lower():
                    return sec, para
    return None


def _paragraphs(lines: list[str]) -> list[str]:
    """Re-join PDF soft-wrapped lines into paragraphs."""
    paras: list[str] = []
    prev_line = ""
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


# Table rows / lines like "Specialist visit (with referral) $65 copay No"
_ROW_RE = re.compile(r"^(.{2,60}?)\s+(\$\d[\d,.]*(?:\s+copay)?)(?:\s+(.*))?$")
_ROW_LABEL_MAX_WORDS = 6
_NOT_A_COPAY = ("deductible", "out-of-pocket", "out of pocket", "coinsurance", "maximum",
                "limit", "premium")


def _cost_rows(paras: list[str]) -> list[dict[str, str]]:
    """Per-service costs: "Label: $X ..." lines and "Label $X ..." table rows."""
    rows = []
    for p in paras:
        m = _LABEL_RE.match(p)
        if m:
            label, value = m.group(1).strip(), m.group(2).strip()
        else:
            m = _ROW_RE.match(p)
            if not m or len(m.group(1).split()) > _ROW_LABEL_MAX_WORDS:
                continue
            label, value = m.group(1).strip(), " ".join(filter(None, [m.group(2), m.group(3)]))
        if value.startswith("$") and not any(w in label.lower() for w in _NOT_A_COPAY):
            rows.append({"service": label, "amount": value})
    return rows


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
    overview = _find_section(sections, "overview", "plan summary", "plan information",
                             "about this", "summary of benefits")
    if overview:
        summary.plan_overview = "\n".join(_paragraphs(overview.body))[:800]
        cite("plan_overview", overview)
    else:
        summary.plan_overview = chunks[0].content[:500]

    # Deductible / coinsurance / out-of-pocket maximum: a section named for the
    # field, else the single line or paragraph that states it
    for attr, keywords in [
        ("deductible", ("deductible",)),
        ("coinsurance", ("coinsurance", "co-insurance")),
        ("out_of_pocket_max", ("out-of-pocket", "out of pocket")),
    ]:
        sec = _find_section(sections, *keywords)
        if sec:
            text = _joined(sec)
        else:
            found = _find_paragraph(sections, *keywords)
            if not found:
                continue
            sec, text = found
        value = {"description": text}
        if attr == "deductible":
            value["page"] = str(sec.page or "")
        setattr(summary, attr, value)
        cite(attr, sec)

    # Copayments: per-service cost rows from the cost section, plus copay notes
    sec = _find_section(sections, "copay", "co-pay", "cost", "you pay", "pay")
    if sec:
        paras = _paragraphs(sec.body)
        summary.copayments = _cost_rows(paras)
        summary.copayments += [
            {"service": "Note", "amount": p} for p in paras
            if "copay" in p.lower() and not _LABEL_RE.match(p) and not p.endswith(":")
        ]
        if summary.copayments:
            cite("copayments", sec)

    # Covered services: "SERVICE: description" paragraphs, else each paragraph
    sec = _find_section(sections, "covered services", "covered benefits", "benefits at a glance",
                        "plan cover", "what is covered")
    if sec:
        paras = [p for p in _paragraphs(sec.body) if not p.endswith(":")]
        items = _labelled(paras) or [(re.split(r"[,.]", p, maxsplit=1)[0][:60], p) for p in paras]
        for label, text in items:
            summary.covered_services.append({"service": label, "description": text})
            for sentence in re.split(r"(?<=\.)\s+", text):
                if "limited to" in sentence.lower():
                    summary.important_limitations.append(f"{label}: {sentence}")
        cite("covered_services", sec)

    # Exclusions: one row per bullet
    sec = _find_section(sections, "exclusion", "not covered", "do not cover", "does not cover",
                        "not cover")
    if sec:
        for bullet in _bullets(_paragraphs(sec.body)):
            name, note = _split_parenthetical(bullet)
            summary.excluded_services.append(
                {"service": name, "description": note or "Not covered"}
            )
        cite("excluded_services", sec)

    # Prior authorization: one row per bullet
    sec = _find_section(sections, "prior auth", "precertification", "pre-certification",
                        "preauthorization", "approval")
    if sec:
        for bullet in _bullets(_paragraphs(sec.body)):
            summary.prior_auth_services.append(
                {"service": bullet, "requirement": "Prior authorization required"}
            )
        cite("prior_auth_services", sec)

    # Network provisions
    sec = _find_section(sections, "network")
    if sec:
        items = _labelled(_paragraphs(sec.body))
        network = [f"{label}: {text}" for label, text in items if "network" in label.lower()]
        summary.network_provisions = {"description": " ".join(network) or _joined(sec)}
        cite("network_provisions", sec)

    # Referral rules: a referral section, else the line/paragraph that states them
    sec = _find_section(sections, "referral")
    if sec:
        summary.referral_requirements = " ".join(_paragraphs(sec.body))
        cite("referral_requirements", sec)
    else:
        found = _find_paragraph(sections, "referral")
        if found:
            sec, text = found
            label, _, rest = text.partition(": ")
            summary.referral_requirements = rest if "referral" in label.lower() and rest else text
            cite("referral_requirements", sec)

    return summary
