"""Changing and deleting documents.

Who may change a document (rename, delete) — narrower than who may read it:
- an individual: their own documents;
- hospital staff: their hospital's patient documents (not policies shared
  with them, which belong to the individual);
- the platform admin: samples it uploaded (preloaded samples live in
  data/policies/ and would be re-ingested at startup, so they are managed
  there instead).
"""

from pathlib import Path

from fastapi import HTTPException

from ..auth.users import HOSPITAL_ROLES, Role, User
from . import records, registry


def can_manage(user: User, entry: dict, upload_dir: Path) -> bool:
    if user.role is Role.INDIVIDUAL:
        return entry.get("owner") == user.username
    if user.role in HOSPITAL_ROLES:
        return bool(entry.get("org_id")) and entry["org_id"] == user.org_id
    if user.role is Role.PLATFORM_ADMIN:
        is_sample = not entry.get("owner") and not entry.get("org_id")
        return is_sample and (upload_dir / entry["filename"]).is_file()
    return False


def rename(document_id: str, display_name: str) -> dict:
    entries = registry.load()
    for e in entries:
        if e["document_id"] == document_id:
            e["display_name"] = display_name
            registry.save(entries)
            return e
    raise HTTPException(404, "Document not found")


def delete(entry: dict, chunk_dir: Path, upload_dir: Path) -> None:
    """Remove the PDF, its chunks, its registry entry, and every share of it
    (hospitals lose access immediately)."""
    doc_id = entry["document_id"]
    registry.save([e for e in registry.load() if e["document_id"] != doc_id])
    (chunk_dir / f"{doc_id}.json").unlink(missing_ok=True)
    source = upload_dir / entry["filename"]
    if source.is_file():
        source.unlink()
    for share in records.shares.all():
        if share.document_id == doc_id:
            records.shares.remove(share.share_id)
