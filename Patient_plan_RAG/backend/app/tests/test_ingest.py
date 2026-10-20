"""Startup registry sync: initial build, re-ingest of stale docs, new PDFs."""

import json
import shutil

import pytest

from backend.app.services import ingest
from backend.app.services.document_processor import CHUNKER_VERSION
from backend.app.tests.conftest import POLICY_PDF


@pytest.fixture
def dirs(tmp_path):
    if not POLICY_PDF.exists():
        pytest.skip("synthetic policy PDF missing")
    d = {name: tmp_path / name for name in ("policies", "uploads", "chunks")}
    for p in d.values():
        p.mkdir()
    shutil.copy(POLICY_PDF, d["policies"])
    return d


def _sync(d):
    return ingest.sync_registry(d["policies"], d["uploads"], d["chunks"])


def _registry(d):
    return json.loads((d["policies"] / "_registry.json").read_text())


def _write_registry(d, registry):
    (d["policies"] / "_registry.json").write_text(json.dumps(registry))


def test_initial_build_uses_content_hash_and_current_version(dirs):
    report = _sync(dirs)
    [entry] = _registry(dirs)
    assert report.added == [entry["document_id"]] == [ingest.content_id(POLICY_PDF)]
    assert entry["chunker_version"] == CHUNKER_VERSION
    assert (dirs["chunks"] / f"{entry['document_id']}.json").exists()


def test_second_sync_is_a_no_op(dirs):
    _sync(dirs)
    before = (dirs["policies"] / "_registry.json").read_text()
    report = _sync(dirs)
    assert report.added == report.reingested == []
    assert (dirs["policies"] / "_registry.json").read_text() == before


def test_stale_entry_is_reingested_keeping_id_and_metadata(dirs):
    _sync(dirs)
    [entry] = _registry(dirs)
    doc_id = entry["document_id"]
    entry.update(chunker_version=0, plan_name="Custom name", chunk_count=999)
    _write_registry(dirs, [entry])
    (dirs["chunks"] / f"{doc_id}.json").write_text("[]")

    report = _sync(dirs)
    [after] = _registry(dirs)
    assert report.reingested == [doc_id]
    assert after["document_id"] == doc_id
    assert after["chunker_version"] == CHUNKER_VERSION
    assert after["plan_name"] == "Custom name"           # kept
    assert after["insurer_name"] == "Apex Health Insurance"  # extracted
    assert after["chunk_count"] == len(json.loads((dirs["chunks"] / f"{doc_id}.json").read_text())) > 0


def test_missing_chunk_file_triggers_reingest(dirs):
    _sync(dirs)
    doc_id = _registry(dirs)[0]["document_id"]
    (dirs["chunks"] / f"{doc_id}.json").unlink()
    assert _sync(dirs).reingested == [doc_id]
    assert (dirs["chunks"] / f"{doc_id}.json").exists()


def test_uploaded_document_is_reingested_from_uploads(dirs):
    shutil.copy(POLICY_PDF, dirs["uploads"] / "abcd1234_mine.pdf")
    (dirs["policies"] / POLICY_PDF.name).unlink()
    _write_registry(dirs, [{"document_id": "upload001", "filename": "abcd1234_mine.pdf",
                            "status": "completed", "is_synthetic": False}])
    assert _sync(dirs).reingested == ["upload001"]
    [entry] = _registry(dirs)
    assert entry["chunk_count"] > 0 and entry["is_synthetic"] is False


def test_entry_without_source_is_left_untouched(dirs):
    ghost = {"document_id": "ghost001", "filename": "gone.pdf", "status": "completed"}
    _write_registry(dirs, [ghost])
    report = _sync(dirs)
    assert report.missing_source == ["ghost001"]
    assert _registry(dirs)[0] == ghost


def test_new_pdf_in_policy_dir_is_added(dirs):
    _sync(dirs)
    # a different PDF: same text, different bytes
    other = dirs["policies"] / "second_plan.pdf"
    other.write_bytes(POLICY_PDF.read_bytes() + b"\n% padding")
    report = _sync(dirs)
    assert report.added == [ingest.content_id(other)]
    assert {e["filename"] for e in _registry(dirs)} == {POLICY_PDF.name, "second_plan.pdf"}


def test_duplicate_bytes_under_new_name_are_skipped(dirs):
    _sync(dirs)
    shutil.copy(POLICY_PDF, dirs["policies"] / "copy.pdf")
    assert _sync(dirs).added == []
    assert len(_registry(dirs)) == 1


def test_failed_document_is_not_retried_until_version_bump(dirs, monkeypatch):
    (dirs["policies"] / "broken.pdf").write_bytes(b"%PDF-1.4 garbage")
    _sync(dirs)
    broken = next(e for e in _registry(dirs) if e["filename"] == "broken.pdf")
    assert broken["status"] == "failed"
    assert broken["chunker_version"] == CHUNKER_VERSION
    assert _sync(dirs).reingested == []
    monkeypatch.setattr(ingest, "CHUNKER_VERSION", CHUNKER_VERSION + 1)
    assert broken["document_id"] in _sync(dirs).reingested


def test_reingest_keeps_document_owner(dirs):
    shutil.copy(POLICY_PDF, dirs["uploads"] / "abcd1234_mine.pdf")
    _write_registry(dirs, [{"document_id": "upload002", "filename": "abcd1234_mine.pdf",
                            "status": "completed", "owner": "member@example.com"}])
    _sync(dirs)
    entry = next(e for e in _registry(dirs) if e["document_id"] == "upload002")
    assert entry["owner"] == "member@example.com"
