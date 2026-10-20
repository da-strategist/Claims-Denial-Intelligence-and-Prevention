"""Which documents a user may see, and which they search by default.

A registry entry is one of:
- a **sample** (no `owner`, no `org_id`): synthetic demo policy, readable by
  every signed-in user, searched only when explicitly selected;
- an **individual's** document (`owner` = their username): visible to them,
  and to a hospital they shared it with;
- a **hospital patient's** document (`org_id` + `patient_id`): visible to
  that hospital's staff only.

Platform admins see samples only: running the platform needs no access to
anyone's policy. A document the user may not see is reported as "not found",
exactly like a missing one, so IDs cannot be probed.
"""

from fastapi import HTTPException

from ..services import records
from .users import HOSPITAL_ROLES, Role, User


def is_sample(entry: dict) -> bool:
    return not entry.get("owner") and not entry.get("org_id")


class Access:
    """One user's view, with the hospital's shares loaded once."""

    def __init__(self, user: User):
        self.user = user
        self.shared: dict[str, records.Share] = {}
        if user.role in HOSPITAL_ROLES:
            self.shared = {s.document_id: s for s in records.shares.all()
                           if s.org_id == user.org_id}

    def can(self, entry: dict) -> bool:
        if is_sample(entry):
            return True
        user = self.user
        if user.role is Role.INDIVIDUAL:
            return entry.get("owner") == user.username
        if user.role in HOSPITAL_ROLES:
            if entry.get("org_id"):
                return entry["org_id"] == user.org_id
            return entry["document_id"] in self.shared
        return False

    def visible(self, registry: list[dict]) -> list[dict]:
        return [e for e in registry if self.can(e)]

    def entry_or_404(self, registry: list[dict], document_id: str) -> dict:
        for entry in registry:
            if entry["document_id"] == document_id and self.can(entry):
                return entry
        raise HTTPException(404, "Document not found")

    def patient_or_404(self, patient_id: str) -> records.Patient:
        patient = records.patients.get(patient_id)
        if patient is None or self.user.role not in HOSPITAL_ROLES or patient.org_id != self.user.org_id:
            raise HTTPException(404, "Patient not found")
        return patient

    def patient_document_ids(self, registry: list[dict], patient_id: str) -> set[str]:
        """A patient's documents: uploaded by the hospital, or shared with it
        by the patient and filed under this patient record."""
        uploaded = {e["document_id"] for e in registry
                    if e.get("org_id") == self.user.org_id and e.get("patient_id") == patient_id}
        filed = {doc_id for doc_id, s in self.shared.items() if s.patient_id == patient_id}
        return uploaded | filed

    def default_search_ids(self, registry: list[dict], patient_id: str | None) -> set[str]:
        """What a question searches when no single document is chosen.

        Individuals: their own documents (samples only when selected).
        Hospital staff: one patient's documents — never across patients.
        """
        if self.user.role is Role.INDIVIDUAL:
            return {e["document_id"] for e in registry if e.get("owner") == self.user.username}
        if self.user.role in HOSPITAL_ROLES and patient_id:
            return self.patient_document_ids(registry, patient_id)
        return set()


# Convenience wrappers used by routers

def accessible_ids(user: User, registry: list[dict]) -> set[str]:
    return {e["document_id"] for e in Access(user).visible(registry)}


def entry_or_404(user: User, registry: list[dict], document_id: str) -> dict:
    return Access(user).entry_or_404(registry, document_id)


def can_access(user: User, entry: dict) -> bool:
    return Access(user).can(entry)
