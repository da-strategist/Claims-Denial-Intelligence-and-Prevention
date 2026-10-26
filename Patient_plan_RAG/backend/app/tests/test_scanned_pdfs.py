"""Scanned (image-only) PDFs: read by OCR when available, otherwise refused
with a clear message; partly readable documents say which pages are missing;
passages read by OCR are marked in citations."""

import io
import shutil

import pytest
from pypdf import PdfReader, PdfWriter

from backend.app.services import document_processor, ocr
from backend.app.tests.conftest import POLICY_PDF

SCANNED_TEXT = (
    "SCHEDULE OF BENEFITS\nPhysical therapy is covered after the deductible for up to "
    "20 visits per calendar year. Prior authorization is required after 12 visits."
)


def _pdf(blank_pages: int = 1, text_pages: int = 0) -> bytes:
    """`text_pages` real pages from the synthetic policy, then blank (scan-like) pages."""
    writer = PdfWriter()
    for page in PdfReader(POLICY_PDF).pages[:text_pages]:
        writer.add_page(page)
    for _ in range(blank_pages):
        writer.add_blank_page(612, 792)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _upload(client, data: bytes, name="scan.pdf"):
    return client.post("/api/policies/upload", files={"file": (name, data, "application/pdf")})


@pytest.fixture
def no_ocr(monkeypatch):
    monkeypatch.setattr(ocr, "available", lambda: False)


@pytest.fixture
def fake_ocr(monkeypatch):
    """OCR 'reads' SCANNED_TEXT from every scanned page."""
    monkeypatch.setattr(ocr, "available", lambda: True)
    monkeypatch.setattr(ocr, "read_page", lambda path, n: SCANNED_TEXT)


def test_scanned_pdf_without_ocr_is_refused_with_an_explanation(client, data_dirs, no_ocr):
    before = client.get("/api/policies").json()
    r = _upload(client, _pdf(blank_pages=2))
    assert r.status_code == 422
    assert "scanned or photographed" in r.json()["detail"]
    assert "selectable text" in r.json()["detail"]
    assert client.get("/api/policies").json() == before
    assert not list(data_dirs["uploads"].iterdir())


def test_unreadable_scan_after_ocr_is_refused(client, monkeypatch):
    monkeypatch.setattr(ocr, "available", lambda: True)
    monkeypatch.setattr(ocr, "read_page", lambda path, n: "~ .")  # noise, not text
    r = _upload(client, _pdf(blank_pages=1))
    assert r.status_code == 422 and "too unclear to read" in r.json()["detail"]


def test_partly_readable_document_lists_the_missing_pages(client, no_ocr):
    r = _upload(client, _pdf(text_pages=2, blank_pages=1))
    assert r.status_code == 200
    body = r.json()
    assert (body["status"], body["unreadable_pages"], body["ocr_pages"]) == ("partial", [3], [])
    assert "Page 3 could not be read" in body["message"]
    doc = client.get(f"/api/policies/{body['document_id']}").json()
    assert doc["unreadable_pages"] == [3]


def test_scanned_pages_are_read_by_ocr_and_marked_in_citations(client, fake_ocr):
    r = _upload(client, _pdf(text_pages=1, blank_pages=1))
    body = r.json()
    assert (r.status_code, body["status"], body["ocr_pages"]) == (200, "completed", [2])
    assert "read by text recognition" in body["message"]
    answer = client.post("/api/chat", json={"question": "How many physical therapy visits are covered?",
                                            "policy_id": body["document_id"]}).json()
    scanned = [c for c in answer["citations"] if c["page_number"] == 2]
    assert scanned and all(c["from_scan"] for c in scanned)
    assert all(not c["from_scan"] for c in answer["citations"] if c["page_number"] == 1)


def test_text_pdfs_never_call_ocr(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr, "available", lambda: True)
    monkeypatch.setattr(ocr, "read_page", lambda *a: pytest.fail("OCR called on a text page"))
    doc, chunks = document_processor.process_document(POLICY_PDF, tmp_path)
    assert (doc.status, doc.ocr_pages, doc.unreadable_pages) == ("completed", [], [])
    assert chunks and not any(c.metadata.get("from_scan") for c in chunks)


@pytest.mark.skipif(not shutil.which("tesseract"), reason="tesseract is not installed")
def test_real_ocr_reads_a_rendered_page(tmp_path):
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1700, 2200), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=48)
    for i, line in enumerate(["SCHEDULE OF BENEFITS", "Specialist visit: $65 copay",
                              "Prior authorization is required for MRI"]):
        draw.text((120, 200 + i * 120), line, fill="black", font=font)
    path = tmp_path / "scan.pdf"
    image.save(path, "PDF", resolution=200)
    assert ocr.available()
    text = ocr.read_page(path, 1)
    assert "Specialist" in text and "$65" in text and "authorization" in text



def test_the_same_file_twice_in_one_place_is_refused(client, data_dirs):
    """Same owner (or same patient record): refused, naming the existing copy.
    Another owner may upload the same file."""
    from fastapi.testclient import TestClient
    from backend.app import main
    from backend.app.tests.conftest import sign_in

    alice = sign_in(TestClient(main.app), "alice@example.com")
    data = POLICY_PDF.read_bytes()
    assert _upload(alice, data, "mine.pdf").status_code == 200
    r = _upload(alice, data, "again.pdf")
    assert r.status_code == 409 and "already uploaded here" in r.json()["detail"]
    assert "Gold PPO Plan" in r.json()["detail"]
    assert len([p for p in data_dirs["uploads"].iterdir() if "again" in p.name]) == 0
    bob = sign_in(TestClient(main.app), "bob@example.com")
    assert _upload(bob, data, "bobs.pdf").status_code == 200
