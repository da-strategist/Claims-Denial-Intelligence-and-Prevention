"""Pages set in two columns are read one column at a time; single-column
pages, label/amount lists and tables are read across as before."""

from pathlib import Path

import pytest

pytest.importorskip("pdfplumber")
canvas_mod = pytest.importorskip("reportlab.pdfgen.canvas")

from backend.app.services.document_processor import extract_text_from_pdf  # noqa: E402

LEFT = ["WHAT YOU PAY", "Deductible: $250 per policy year in", "network and $500 out of network for",
        "each insured person, waived at the", "student health center for all visits.",
        "Coinsurance is 20% in network and", "40% out of network after you have", "met the deductible for the year."]
RIGHT = ["EXCLUSIONS", "The plan does not cover injuries from", "intercollegiate sports, cosmetic surgery",
         "or routine dental care, and it does not", "cover eyeglasses for adults over 19.",
         "Claims must be filed within 90 days of", "the date of service, and appeals within", "180 days of a denial of benefits."]


def _pdf(path: Path, draw) -> Path:
    c = canvas_mod.Canvas(str(path), pagesize=(612, 792), invariant=1)
    draw(c)
    c.save()
    return path


def _two_columns(c):
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 740, "Lakeside Student Health Plan 2026 - Member Brochure")  # across the page
    c.setFont("Helvetica", 10)
    for i, (left, right) in enumerate(zip(LEFT, RIGHT)):
        c.drawString(72, 700 - i * 14, left)
        c.drawString(320, 700 - i * 14, right)


def test_two_column_page_is_read_column_by_column(tmp_path):
    [page] = extract_text_from_pdf(_pdf(tmp_path / "two.pdf", _two_columns))
    lines = page["text"].splitlines()
    assert lines == ["Lakeside Student Health Plan 2026 - Member Brochure", *LEFT, *RIGHT]
    assert "WHAT YOU PAY" in page["headings"] or lines[1] == "WHAT YOU PAY"


def test_label_and_amount_list_is_not_split(tmp_path):
    rows = [("Primary care visit", "$25 copay"), ("Specialist visit", "$50 copay"),
            ("Urgent care", "$75 copay"), ("Emergency room", "$300 copay"),
            ("Generic drugs", "$10 copay"), ("Brand drugs", "$40 copay")]

    def draw(c):
        c.setFont("Helvetica", 10)
        c.drawString(72, 740, "Your costs for common services are listed in this table below.")
        for i, (label, amount) in enumerate(rows):
            c.drawString(72, 710 - i * 14, label)
            c.drawString(400, 710 - i * 14, amount)
        for i in range(4):
            c.drawString(72, 610 - i * 14, "Body text that runs across the whole width of the page, "
                                           "as a single-column document does.")

    [page] = extract_text_from_pdf(_pdf(tmp_path / "list.pdf", draw))
    for label, amount in rows:
        assert f"{label} {amount}" in page["text"]


def test_single_column_page_is_unchanged(tmp_path):
    def draw(c):
        c.setFont("Helvetica", 10)
        for i in range(12):
            c.drawString(72, 740 - i * 14, f"Line {i}: covered services include office visits and tests "
                                           f"when medically necessary.")

    [page] = extract_text_from_pdf(_pdf(tmp_path / "one.pdf", draw))
    assert page["text"].splitlines()[0].startswith("Line 0:") and len(page["text"].splitlines()) == 12
