"""The only way routes reach data: the signed-in user's organisation's stores.

Every store and cache is created per organisation (`get_repository(org_id)` and so on).
These dependencies take the organisation from the signed-in account, never from the URL,
a header, or the request body, so a request can only ever touch its own organisation's
data. Routes declare `repo: OrgClaims` and similar; they never call the getters directly.
Claims additionally pass through the account's access scope (data/scoped.py).
"""

from typing import Annotated

from fastapi import Depends

from app.data.audit import AuditLog, get_audit_log
from app.data.corrections import CorrectionStore, get_correction_store
from app.data.drafts import DraftStore, get_draft_store
from app.data.knowledge import KnowledgeBase, get_knowledge_base
from app.data.reference import ReferenceData, get_reference_data
from app.data.registrations import RegistrationStore, get_registration_store
from app.data.repository import get_repository
from app.data.rules import RuleRepository, get_rule_repository
from app.data.scoped import ScopedClaims
from app.services.assistant import NameScrubber, Retriever, get_name_scrubber, get_retriever
from app.services.auth import SignedIn
from app.services.status_snapshot import StatusSnapshot, get_status_snapshot


def current_org_id(user: SignedIn) -> str:
    """The signed-in user's organisation (current_user refuses accounts without one)."""
    return user.organisation_id


OrgId = Annotated[str, Depends(current_org_id)]


def _claims(org_id: OrgId, user: SignedIn) -> ScopedClaims:
    """The organisation's claims as this account may see them (its access scope)."""
    return ScopedClaims(get_repository(org_id), user.effective_scope)


def _rules(org_id: OrgId) -> RuleRepository:
    return get_rule_repository(org_id)


def _corrections(org_id: OrgId) -> CorrectionStore:
    return get_correction_store(org_id)


def _reference(org_id: OrgId) -> ReferenceData:
    return get_reference_data(org_id)


def _drafts(org_id: OrgId) -> DraftStore:
    return get_draft_store(org_id)


def _registrations(org_id: OrgId) -> RegistrationStore:
    return get_registration_store(org_id)


def _snapshot(org_id: OrgId) -> StatusSnapshot:
    return get_status_snapshot(org_id)


def _audit(org_id: OrgId) -> AuditLog:
    return get_audit_log(org_id)


def _knowledge(org_id: OrgId) -> KnowledgeBase:
    return get_knowledge_base(org_id)


def _retriever(org_id: OrgId) -> Retriever:
    return get_retriever(org_id)


def _names(org_id: OrgId) -> NameScrubber:
    return get_name_scrubber(org_id)


OrgClaims = Annotated[ScopedClaims, Depends(_claims)]
OrgRules = Annotated[RuleRepository, Depends(_rules)]
OrgCorrections = Annotated[CorrectionStore, Depends(_corrections)]
OrgReference = Annotated[ReferenceData, Depends(_reference)]
OrgDrafts = Annotated[DraftStore, Depends(_drafts)]
OrgRegistrations = Annotated[RegistrationStore, Depends(_registrations)]
OrgSnapshot = Annotated[StatusSnapshot, Depends(_snapshot)]
OrgAudit = Annotated[AuditLog, Depends(_audit)]
OrgKnowledge = Annotated[KnowledgeBase, Depends(_knowledge)]
OrgRetriever = Annotated[Retriever, Depends(_retriever)]
OrgNames = Annotated[NameScrubber, Depends(_names)]
