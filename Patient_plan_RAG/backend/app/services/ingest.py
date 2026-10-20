"""Keep the registry and chunk files in sync with source PDFs at startup.

- No registry yet: ingest every PDF in the policy directory.
- Registered documents built with an older CHUNKER_VERSION, or completed
  ones whose chunk file is missing, are re-ingested from their source PDF under the same
  document ID. Metadata already on the entry is kept (never overwritten).
- PDFs in the policy directory that are not registered yet are ingested.
- Entries whose source PDF can no longer be found are left untouched.

Preloaded PDFs get content-hash IDs, so rebuilding is idempotent.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from .document_processor import CHUNKER_VERSION, process_document

log = logging.getLogger(__name__)

# Entry fields carried into a re-ingest; extraction only fills empty ones.
_KEPT_FIELDS = (
    "insurer_name", "plan_name", "plan_id", "effective_date", "expiration_date",
    "document_type", "is_synthetic", "metadata", "owner", "org_id", "patient_id",
)


@dataclass
class SyncReport:
    added: list[str] = field(default_factory=list)
    reingested: list[str] = field(default_factory=list)
    missing_source: list[str] = field(default_factory=list)


def content_id(pdf: Path) -> str:
    return hashlib.sha256(pdf.read_bytes()).hexdigest()[:12]


def _find_source(filename: str, search_dirs: list[Path]) -> Path | None:
    for d in search_dirs:
        candidate = d / filename
        if candidate.is_file():
            return candidate
    return None


def sync_registry(policy_dir: Path, upload_dir: Path, chunk_dir: Path) -> SyncReport:
    report = SyncReport()
    registry_path = policy_dir / "_registry.json"
    registry: list[dict] = (
        json.loads(registry_path.read_text()) if registry_path.exists() else []
    )
    changed = not registry_path.exists()

    # Re-ingest stale or chunk-less entries in place
    for i, entry in enumerate(registry):
        doc_id = entry["document_id"]
        stale = entry.get("chunker_version", 0) < CHUNKER_VERSION
        chunks_missing = (
            entry.get("status") == "completed"
            and not (chunk_dir / f"{doc_id}.json").exists()
        )
        if not (stale or chunks_missing):
            continue
        source = _find_source(entry["filename"], [upload_dir, policy_dir])
        if source is None:
            log.warning("Cannot re-ingest %s: source %s not found", doc_id, entry["filename"])
            report.missing_source.append(doc_id)
            continue
        kept = {k: entry[k] for k in _KEPT_FIELDS if entry.get(k) not in (None, "", {})}
        doc, _ = process_document(source, chunk_dir, document_id=doc_id, metadata=kept)
        registry[i] = doc.model_dump(mode="json")
        report.reingested.append(doc_id)
        changed = True

    # Ingest PDFs in the policy directory that are not registered yet
    known_names = {e["filename"] for e in registry}
    known_ids = {e["document_id"] for e in registry}
    for pdf in sorted(policy_dir.glob("*.pdf")):
        if pdf.name in known_names:
            continue
        doc_id = content_id(pdf)
        if doc_id in known_ids:  # same bytes already registered under another name
            continue
        doc, _ = process_document(pdf, chunk_dir, document_id=doc_id)
        registry.append(doc.model_dump(mode="json"))
        known_ids.add(doc_id)
        report.added.append(doc_id)
        changed = True

    if changed:
        registry_path.write_text(json.dumps(registry, indent=2, default=str))
    if report.added or report.reingested:
        log.info("Registry sync: added %s, re-ingested %s", report.added, report.reingested)
    return report
