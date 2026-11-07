"""The validation set itself is well formed. (The app is scored on it with
`python -m backend.app.tests.validation_eval`, not here: it's a measurement,
not a regression gate, and isn't used to tune the app.)"""

from pathlib import Path

import pytest

from backend.app.tests.validation_eval import VALIDATION_DIR
from synthetic_data.validation import generate
from synthetic_data.validation.ground_truth import problems
from synthetic_data.validation.questions import METADATA, QUESTIONS


def test_ground_truth_phrases_come_from_the_documents():
    assert problems() == []


def test_every_document_is_generated_and_has_plan_details():
    names = {p.name for p in VALIDATION_DIR.glob("*.pdf")}
    assert names == set(METADATA)
    assert {d for q in QUESTIONS for d in q["docs"]} <= names


def test_generation_is_deterministic(tmp_path: Path):
    for path in generate.generate(tmp_path):
        if "scanned" not in path.name:  # scans embed image encoder output
            assert path.read_bytes() == (VALIDATION_DIR / path.name).read_bytes(), path.name


def test_scanned_copy_has_no_text_layer():
    pytest.importorskip("pdfplumber")
    from backend.app.services.document_processor import extract_text_from_pdf

    pages = extract_text_from_pdf(VALIDATION_DIR / "meridian_catastrophic_2026_scanned.pdf")
    assert pages and all(not p["text"].strip() for p in pages)
