"""PDF extraction and text chunking pipeline."""

import hashlib
import json
import re
import uuid
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from ..models.policy import DocumentChunk, DocumentStatus, PolicyDocument


# Bump whenever chunking or metadata extraction changes: documents ingested
# with an older version are re-ingested at startup (services/ingest.py).
CHUNKER_VERSION = 3  # 2: font-based headings; 3: "Issued by"/"Program"/org title-line metadata


def _generate_chunk_id(document_id: str, index: int) -> str:
    raw = f"{document_id}:{index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# A line is a heading if its font is this much larger than the page's body
# text, or if it is entirely bold and short.
_HEADING_SIZE_RATIO = 1.15
_BOLD_HEADING_MAX_WORDS = 12


def _font_headings(page) -> list[str]:
    """Lines set in a heading font (larger than body text, or all bold)."""
    sizes = Counter(round(c["size"], 1) for c in page.chars if c["text"].strip())
    if not sizes:
        return []
    body_size = sizes.most_common(1)[0][0]
    headings = []
    for line in page.extract_text_lines():
        chars = [c for c in line["chars"] if c["text"].strip()]
        if not chars:
            continue
        avg_size = sum(c["size"] for c in chars) / len(chars)
        all_bold = all("bold" in c["fontname"].lower() for c in chars)
        text = line["text"].strip()
        if avg_size >= body_size * _HEADING_SIZE_RATIO or (
            all_bold and len(text.split()) <= _BOLD_HEADING_MAX_WORDS
        ):
            headings.append(text)
    return headings


def extract_text_from_pdf(pdf_path: Path) -> list[dict]:
    """Extract text page-by-page using pdfplumber, fallback to pypdf.

    Each page is {"page_number", "text", "headings"}; headings are lines whose
    font marks them as headings (pdfplumber only; empty with pypdf).
    """
    pages: list[dict] = []
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                pages.append({"page_number": i, "text": text.strip(),
                              "headings": _font_headings(page)})
    except Exception:
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(pdf_path))
            for i, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                pages.append({"page_number": i, "text": text.strip(), "headings": []})
        except Exception as exc:
            raise RuntimeError(f"Cannot extract text from {pdf_path.name}: {exc}") from exc
    return pages


_HEADING_RE = re.compile(
    r"^(SECTION|ARTICLE|PART|CHAPTER|COVERAGE|EXCLUSION|BENEFIT|LIMITATION|"
    r"PRIOR\s+AUTH|PRE-?CERTIFICATION|APPEAL|GRIEVANCE|DEFINITIONS?|"
    r"GENERAL\s+PROVISIONS?|ELIGIBILITY|COST[\s-]SHARING|"
    r"OUT[\s-]OF[\s-]POCKET|DEDUCTIBLE|CO-?PAY|CO-?INSURANCE|"
    r"NETWORK|IN[\s-]NETWORK|OUT[\s-]OF[\s-]NETWORK|EMERGENCY|"
    r"PRESCRIPTION|MENTAL\s+HEALTH|PREVENTIVE|MATERNITY|PEDIATRIC|"
    r"REHABILITATION|DURABLE\s+MEDICAL|HOME\s+HEALTH|HOSPICE|"
    r"SKILLED\s+NURSING|SUMMARY\s+OF\s+BENEFITS|PLAN\s+OVERVIEW|"
    r"TABLE\s+OF\s+CONTENTS|MEMBER\s+RIGHTS|CLAIMS?|COORDINATION)\w*\b",
    re.IGNORECASE,
)


def _detect_section(line: str) -> str:
    """Heuristic section heading detection.

    Headings are short standalone lines. Body lines that merely start with a
    label ("Deductible: The amount...", "PREVENTIVE CARE: Covered at...") and
    long all-caps sentences (disclaimer banners) are not headings.
    """
    stripped = line.strip()
    if len(stripped) > 80 or len(stripped) < 3:
        return ""
    if len(stripped.split()) > 8 or stripped.endswith((".", ",", ";")):
        return ""
    if stripped.isupper():
        return stripped
    if _HEADING_RE.match(stripped) and ":" not in stripped and _is_title_case(stripped):
        return stripped
    return ""


def _is_title_case(text: str) -> bool:
    """'Prior Authorization Requirements' yes; 'Coverage applies to dependents' no."""
    words = [w for w in text.split() if w[0].isalpha() and len(w) > 3]
    return all(w[0].isupper() for w in words)


def _clean_line(line: str) -> str:
    """Normalise PDF extraction artefacts (e.g. unmapped bullet glyphs)."""
    return line.replace("(cid:127)", "•").strip()


def _overlap_lines(lines: list[str], chunk_overlap: int) -> list[str]:
    """Trailing whole lines of the previous chunk, up to ~chunk_overlap chars."""
    kept: list[str] = []
    size = 0
    for line in reversed(lines):
        if kept and size + len(line) > chunk_overlap:
            break
        kept.insert(0, line)
        size += len(line) + 1
    return kept if size <= chunk_overlap * 2 else []


_DATE_FORMATS = ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%Y-%m-%d")


def _parse_date(text: str) -> date | None:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _labelled_value(text: str, *labels: str) -> str:
    """Value after the first 'Label: value' match on a line, else ''."""
    for label in labels:
        m = re.search(rf"(?im)^.*?\b{label}\s*[:#]\s*(.+?)\s*$", text)
        if m:
            return m.group(1)
    return ""


_ORG_WORD_RE = re.compile(r"\b(Insurance|Health|Mutual|Assurance|Company|Inc)\b")


def extract_policy_metadata(pages: list[dict]) -> dict:
    """Pull insurer, plan name/ID and dates from the first pages.

    Only explicitly stated values are returned (verbatim); anything not found
    is omitted rather than guessed.
    """
    text = "\n".join(p["text"] for p in pages[:2])
    meta: dict = {}

    plan_id = _labelled_value(text, r"Plan\s+ID", r"Plan\s+(?:Number|No\.?)")
    if plan_id:
        meta["plan_id"] = plan_id.split()[0]

    insurer = _labelled_value(text, "Insurer", "Carrier", r"Insurance\s+Company", r"Issued\s+by")
    plan_name = _labelled_value(text, r"Plan\s+Name", "Program")
    if not (insurer and plan_name):
        # "Apex Health Insurance — Gold PPO Plan": the left side must look like
        # an organisation, so "Gold PPO Plan — Summary of Benefits" is skipped
        for m in re.finditer(r"(?m)^\s*([^\n:|]{3,80}?)\s+[—–-]\s+([^\n:|]{3,80}?)\s*$", text):
            if _ORG_WORD_RE.search(m.group(1)):
                insurer = insurer or m.group(1)
                plan_name = plan_name or m.group(2)
                break
    if insurer:
        meta["insurer_name"] = insurer
    if plan_name:
        meta["plan_name"] = plan_name

    for key, labels in [
        ("effective_date", (r"Effective\s+Date",)),
        ("expiration_date", (r"Expiration\s+Date", r"Termination\s+Date", r"End\s+Date")),
    ]:
        parsed = _parse_date(_labelled_value(text, *labels))
        if parsed:
            meta[key] = parsed
    return meta


def chunk_text(
    pages: list[dict],
    document_id: str,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> list[DocumentChunk]:
    """Split extracted pages into chunks that follow section boundaries.

    A new chunk starts at every section heading (consecutive headings stay
    together, the last one labels the chunk). Sections longer than chunk_size
    are split on line boundaries, carrying whole trailing lines as overlap.
    """
    chunks: list[DocumentChunk] = []
    section = ""
    buffer: list[str] = []
    buffer_page = pages[0]["page_number"] if pages else 1
    has_body = False  # buffer holds at least one non-heading, non-overlap line

    def flush() -> None:
        content = "\n".join(buffer).strip()
        if content:
            chunks.append(DocumentChunk(
                chunk_id=_generate_chunk_id(document_id, len(chunks)),
                document_id=document_id,
                page_number=buffer_page,
                section_heading=section,
                content=content,
                content_lower=content.lower(),
            ))

    for page_data in pages:
        page_num = page_data["page_number"]
        font_headings = {_clean_line(h) for h in page_data.get("headings", [])}
        for raw_line in page_data["text"].split("\n"):
            line = _clean_line(raw_line)
            if not line:
                continue

            heading = line if line in font_headings else _detect_section(line)
            if heading:
                if has_body:
                    flush()
                    buffer, has_body = [], False
                if not buffer:
                    buffer_page = page_num
                section = heading
                buffer.append(line)
                continue

            if has_body and len("\n".join(buffer)) + len(line) + 1 > chunk_size:
                flush()
                buffer = _overlap_lines(buffer, chunk_overlap) if chunk_overlap > 0 else []
                buffer_page = page_num
            elif not buffer:
                buffer_page = page_num
            buffer.append(line)
            has_body = True

    if has_body:
        flush()

    return chunks


def process_document(
    pdf_path: Path,
    chunk_dir: Path,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
    metadata: dict | None = None,
    document_id: str | None = None,
) -> tuple[PolicyDocument, list[DocumentChunk]]:
    """End-to-end: extract → chunk → persist chunks as JSON."""
    document_id = document_id or uuid.uuid4().hex[:12]

    doc = PolicyDocument(
        document_id=document_id,
        filename=pdf_path.name,
        status=DocumentStatus.PROCESSING,
        **(metadata or {}),
    )
    # Recorded even on failure, so a broken file is retried only after a bump
    doc.chunker_version = CHUNKER_VERSION

    try:
        pages = extract_text_from_pdf(pdf_path)
        doc.page_count = len(pages)

        # Fill metadata stated in the document, without overriding caller values
        for key, value in extract_policy_metadata(pages).items():
            if not getattr(doc, key):
                setattr(doc, key, value)

        chunks = chunk_text(pages, document_id, chunk_size, chunk_overlap)
        doc.chunk_count = len(chunks)

        # Persist chunks
        chunk_dir.mkdir(parents=True, exist_ok=True)
        chunk_file = chunk_dir / f"{document_id}.json"
        chunk_file.write_text(
            json.dumps([c.model_dump() for c in chunks], indent=2, default=str)
        )

        doc.status = DocumentStatus.COMPLETED
    except Exception as exc:
        doc.status = DocumentStatus.FAILED
        doc.error_message = str(exc)
        chunks = []

    return doc, chunks
