"""Shared fixtures: the synthetic policy PDF and its chunks."""

from pathlib import Path

import pytest

from backend.app.services.document_processor import chunk_text, extract_text_from_pdf

POLICY_PDF = (
    Path(__file__).resolve().parents[3] / "data" / "policies" / "apex_health_gold_ppo_2025.pdf"
)


@pytest.fixture(scope="session")
def policy_pages() -> list[dict]:
    if not POLICY_PDF.exists():
        pytest.skip("synthetic policy PDF missing; run python -m synthetic_data.generate_policy")
    return extract_text_from_pdf(POLICY_PDF)


@pytest.fixture(scope="session")
def policy_chunks(policy_pages):
    return chunk_text(policy_pages, "testdoc")
