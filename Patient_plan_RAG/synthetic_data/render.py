"""Render a synthetic policy spec to PDF.

A spec is a dict:
    filename:     output file name
    title_lines:  [(text, "title" | "subtitle" | "body"), ...]
    sections:     [(heading, [block, ...]), ...]
where a block is a paragraph string, "" for a small gap,
{"table": [[cell, ...], ...]} (first row is the header), or
{"note": text} (small footnote text). Optional "columns": 2 lays the body out
in two columns, as many brochures and student plan booklets do.

PDFs are written with reportlab's invariant mode (fixed timestamps and IDs),
so regenerating unchanged content produces identical bytes and therefore the
same content-hash document ID at ingest.
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("PolicyTitle", parent=base["Title"], fontSize=18, spaceAfter=20),
        "subtitle": ParagraphStyle(
            "PolicyHeading", parent=base["Heading2"], fontSize=13, spaceAfter=8,
            spaceBefore=16, textColor=colors.HexColor("#1a365d"),
        ),
        "body": ParagraphStyle(
            "PolicyBody", parent=base["Normal"], fontSize=10, leading=14, spaceAfter=4,
        ),
        "note": ParagraphStyle(
            "PolicyNote", parent=base["Normal"], fontSize=7.5, leading=9.5, spaceAfter=3,
            textColor=colors.HexColor("#475569"),
        ),
    }


def _table(rows: list[list[str]], body_style: ParagraphStyle) -> Table:
    data = [[Paragraph(cell, body_style) for cell in row] for row in rows]
    table = Table(data, hAlign="LEFT", repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def render_policy(spec: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / spec["filename"]
    margins = dict(topMargin=0.75 * inch, bottomMargin=0.75 * inch,
                   leftMargin=1 * inch, rightMargin=1 * inch)
    if spec.get("columns") == 2:
        doc = BaseDocTemplate(str(output_path), pagesize=letter, invariant=1, **margins)
        gap = 0.3 * inch
        width = (doc.width - gap) / 2
        doc.addPageTemplates([PageTemplate(id="two", frames=[
            Frame(doc.leftMargin, doc.bottomMargin, width, doc.height, id="left"),
            Frame(doc.leftMargin + width + gap, doc.bottomMargin, width, doc.height, id="right"),
        ])])
    else:
        doc = SimpleDocTemplate(str(output_path), pagesize=letter, invariant=1, **margins)
    styles = _styles()

    elements = [Paragraph(text, styles[style]) for text, style in spec["title_lines"]]
    elements.append(Spacer(1, 20))
    for heading, blocks in spec["sections"]:
        elements.append(Paragraph(heading, styles["subtitle"]))
        for block in blocks:
            if block == "":
                elements.append(Spacer(1, 6))
            elif isinstance(block, dict) and "note" in block:
                elements.append(Paragraph(block["note"], styles["note"]))
            elif isinstance(block, dict):
                elements.append(_table(block["table"], styles["body"]))
                elements.append(Spacer(1, 6))
            else:
                elements.append(Paragraph(block, styles["body"]))

    doc.build(elements)
    return output_path


def scan_copy(pdf_path: Path, output_path: Path, dpi: int = 150, seed: int = 7) -> Path:
    """An image-only copy of a PDF, as if printed and scanned: grayscale pages,
    a slight tilt and speckle noise, with no text layer. Deterministic."""
    import random

    import pypdfium2
    from PIL import Image, ImageFilter

    rng = random.Random(seed)
    pdf = pypdfium2.PdfDocument(str(pdf_path))
    pages = []
    try:
        for page in pdf:
            img = page.render(scale=dpi / 72).to_pil().convert("L")
            img = img.rotate(rng.uniform(-0.8, 0.8), expand=False, fillcolor=255)
            pixels = img.load()
            w, h = img.size
            for _ in range(w * h // 400):  # speckles
                pixels[rng.randrange(w), rng.randrange(h)] = rng.choice((0, 90, 200))
            pages.append(img.filter(ImageFilter.GaussianBlur(0.4)))
    finally:
        pdf.close()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(output_path, "PDF", resolution=dpi, save_all=True, append_images=pages[1:])
    return output_path
