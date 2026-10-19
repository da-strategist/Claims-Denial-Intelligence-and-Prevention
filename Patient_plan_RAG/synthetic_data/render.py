"""Render a synthetic policy spec to PDF.

A spec is a dict:
    filename:     output file name
    title_lines:  [(text, "title" | "subtitle" | "body"), ...]
    sections:     [(heading, [block, ...]), ...]
where a block is a paragraph string, "" for a small gap, or
{"table": [[cell, ...], ...]} (first row is the header).

PDFs are written with reportlab's invariant mode (fixed timestamps and IDs),
so regenerating unchanged content produces identical bytes and therefore the
same content-hash document ID at ingest.
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


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
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        invariant=1,
    )
    styles = _styles()

    elements = [Paragraph(text, styles[style]) for text, style in spec["title_lines"]]
    elements.append(Spacer(1, 20))
    for heading, blocks in spec["sections"]:
        elements.append(Paragraph(heading, styles["subtitle"]))
        for block in blocks:
            if block == "":
                elements.append(Spacer(1, 6))
            elif isinstance(block, dict):
                elements.append(_table(block["table"], styles["body"]))
                elements.append(Spacer(1, 6))
            else:
                elements.append(Paragraph(block, styles["body"]))

    doc.build(elements)
    return output_path
