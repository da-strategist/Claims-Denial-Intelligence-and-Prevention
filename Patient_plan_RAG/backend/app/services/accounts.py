"""Deleting an individual's account or a provider organisation, with
everything that belongs to it. Used by the individual (delete my account)
and by the platform admin (spam and rejected sign-ups).

The audit log is append-only: past entries are kept, and the request that
deletes is itself recorded.
"""

from pathlib import Path

from ..auth.sessions import sessions
from ..auth.users import user_store
from . import documents, records, registry


def delete_individual(username: str, chunk_dir: Path, upload_dir: Path) -> None:
    """Policies (files, search index), shares (providers lose access at once),
    providers list and the account. Patient records a provider created from
    their shares stay with the provider, without the shared policies."""
    for entry in registry.load():
        if entry.get("owner") == username:
            documents.delete(entry, chunk_dir, upload_dir)
    for s in records.shares.all():
        if s.shared_by == username:
            records.shares.remove(s.share_id)
    for p in records.providers.all():
        if p.owner == username:
            records.providers.remove(p.provider_id)
    sessions.end_all_for(username)
    user_store.delete(username)


def delete_org(org_id: str, chunk_dir: Path, upload_dir: Path) -> None:
    """A provider and all it holds: staff accounts, patient records, the
    documents it uploaded, checklists. Policies individuals shared with it
    stay theirs (the shares end); their connections to it become typed
    entries in their providers list."""
    for entry in registry.load():
        if entry.get("org_id") == org_id:
            documents.delete(entry, chunk_dir, upload_dir)
    for store, attr in ((records.patients, "patient_id"), (records.checklists, "checklist_id"),
                        (records.shares, "share_id")):
        for item in store.all():
            if item.org_id == org_id:
                store.remove(getattr(item, attr))
    for link in records.providers.all():
        if link.org_id == org_id:
            records.providers.update(link.provider_id, org_id=None, patient_id=None)
    for u in user_store.all():
        if u.org_id == org_id:
            sessions.end_all_for(u.username)
            user_store.delete(u.username)
    records.orgs.remove(org_id)
