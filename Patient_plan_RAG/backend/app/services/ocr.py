"""Optical character recognition (OCR) for scanned pages.

Uses Tesseract, a separate program (`brew install tesseract` on macOS,
`apt install tesseract-ocr` on Debian/Ubuntu) driven through pytesseract.
When it isn't installed, scanned pages are reported as unreadable instead of
being read. Set OCR_ENABLED=false to turn OCR off.
"""

import os
import shutil
from pathlib import Path

OCR_DPI = 300  # render resolution: Tesseract reads 300 dpi page images well


def available() -> bool:
    if os.getenv("OCR_ENABLED", "true").lower() == "false" or not shutil.which("tesseract"):
        return False
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    return True


def read_page(pdf_path: Path, page_number: int) -> str:
    """The text Tesseract reads on one page (1-based) of the PDF."""
    import pypdfium2
    import pytesseract

    pdf = pypdfium2.PdfDocument(str(pdf_path))
    try:
        image = pdf[page_number - 1].render(scale=OCR_DPI / 72).to_pil()
    finally:
        pdf.close()
    return pytesseract.image_to_string(image).strip()
