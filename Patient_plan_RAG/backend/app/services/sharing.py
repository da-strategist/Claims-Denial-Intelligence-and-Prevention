"""When an individual shares a policy with a provider, the provider gets a
patient record for them, so the person appears in the patient list and the
chat / coverage pickers, and questions about them search what they shared.

Sharing also connects the individual to the provider (their "My providers"
list). A connection made without sharing does not create a record; staff can
create or attach one themselves.
"""

from ..auth.users import user_store
from . import records

KIND_FOR_CATEGORY = {"hospital", "clinic", "pharmacy", "laboratory", "imaging", "dental"}


def ensure_connection(owner: str, org: records.Org) -> records.Provider:
    """The individual's connection to the provider; a typed entry with the
    provider's name is linked rather than listed twice."""
    link = records.connection(owner, org.org_id)
    if link is not None:
        return link
    kind = org.category if org.category in KIND_FOR_CATEGORY else "other"
    typed = next((p for p in records.providers.all() if p.owner == owner and not p.org_id
                  and p.name.strip().lower() == org.name.strip().lower()), None)
    if typed:
        return records.providers.update(typed.provider_id, org_id=org.org_id, name=org.name,
                                        kind=kind, connected_at=records._now())
    return records.providers.add(records.Provider(
        records.new_id(), owner, org.name, kind, org_id=org.org_id, connected_at=records._now()))


def patient_record_for(owner: str, org: records.Org) -> records.Patient:
    """The provider's patient record for this individual, created (or
    restored from the archive) if needed, and attached to the connection."""
    link = ensure_connection(owner, org)
    patient = records.patients.get(link.patient_id) if link.patient_id else None
    if patient is None or patient.org_id != org.org_id:
        person = user_store.get(owner)
        patient = records.patients.add(records.Patient(
            records.new_id(), org.org_id, (person.full_name if person else "") or owner,
            linked_username=owner))
        records.providers.update(link.provider_id, patient_id=patient.patient_id)
    elif patient.archived:
        patient = records.patients.update(patient.patient_id, archived=False)
    return patient


def refresh_names(username: str | None = None) -> int:
    """Records created before the person gave their name are named after
    their email; give them the profile name once there is one (run at startup
    and when a profile changes). Records staff have renamed are left alone.
    Returns the number renamed."""
    renamed = 0
    for patient in records.patients.all():
        if not patient.linked_username or patient.name != patient.linked_username:
            continue
        if username and patient.linked_username != username:
            continue
        person = user_store.get(patient.linked_username)
        if person and person.full_name:
            records.patients.update(patient.patient_id, name=person.full_name)
            renamed += 1
    return renamed


def backfill() -> int:
    """Give shares made before automatic records one (run at startup).

    Only shares with no patient and no connection yet: once a connection
    exists, staff decisions (unfiling, re-filing) are left alone.
    Returns the number of shares filed.
    """
    filed = 0
    for share in records.shares.all():
        if share.patient_id or records.connection(share.shared_by, share.org_id):
            continue
        org = records.orgs.get(share.org_id)
        if org is None or not org.usable or user_store.get(share.shared_by) is None:
            continue
        patient = patient_record_for(share.shared_by, org)
        for s in records.shares.all():  # every unfiled share from this person to this provider
            if s.org_id == org.org_id and s.shared_by == share.shared_by and s.patient_id is None:
                records.shares.update(s.share_id, patient_id=patient.patient_id)
                filed += 1
    return filed
