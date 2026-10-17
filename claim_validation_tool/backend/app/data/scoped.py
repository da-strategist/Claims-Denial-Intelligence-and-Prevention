"""The organisation's claims as one account may see them (need to know).

Routes get a ScopedClaims, never the ClaimsRepository itself (services/org_context.py).
It applies the account's access scope to every read and write: lists and frames hold only
in-scope claims, an out-of-scope claim is "not found", and a claim can only be created
or submitted inside the scope. Each method is written out (no catch-all delegation), so a
method added to the repository isn't reachable here until someone decides how it's scoped.

The patient register stays organisation-wide (anyone may start a claim for any registered
patient), but a patient's claim and denial counts only count what the account can see.
"""

import pandas as pd

from app.data.repository import ClaimsRepository
from app.models import (
    AccessScope,
    Claim,
    ClaimDetail,
    ClaimQuery,
    Department,
    EdiFile,
    Facility,
    Page,
    PatientQuery,
    PatientSummary,
    Payer,
    Provider,
)


class OutOfScopeError(PermissionError):
    """The claim being created or changed is outside the account's access."""


class ScopedClaims:
    def __init__(self, base: ClaimsRepository, scope: AccessScope) -> None:
        self.base = base  # for organisation-wide caches (the validation snapshot)
        self.scope = scope

    # --- Scope ---------------------------------------------------------------

    def _mask(self, frame: pd.DataFrame) -> pd.Series:
        scope = self.scope
        return (
            frame["facility_id"].isin(scope.facilities)
            | frame["department_id"].isin(scope.departments)
            | frame["provider_id"].isin(scope.providers)
        )

    def _visible(self, claim: Claim | None) -> bool:
        return claim is not None and self.scope.allows(
            claim.facility_id, claim.department_id, claim.provider_id
        )

    def _require(self, claim_id: str) -> None:
        if not self._visible(self.base.get_claim(claim_id)):
            raise LookupError(f"Claim {claim_id} not found")

    @property
    def version(self) -> int:
        return self.base.version

    # --- Claims --------------------------------------------------------------

    def list_claims(self, query: ClaimQuery, statuses: pd.DataFrame | None = None) -> Page[Claim]:
        within = self._mask if self.scope.restricted else None
        return self.base.list_claims(query, statuses, within=within)

    def get_claim(self, claim_id: str) -> ClaimDetail | None:
        claim = self.base.get_claim(claim_id)
        return claim if self._visible(claim) else None

    def claims_frame(self, claim_ids: list[str] | None = None) -> pd.DataFrame:
        frame = self.base.claims_frame(claim_ids)
        return frame[self._mask(frame)] if self.scope.restricted else frame

    def denials_frame(self) -> pd.DataFrame:
        denials = self.base.denials_frame()
        if not self.scope.restricted:
            return denials
        return denials[denials["claim_id"].isin(self.claims_frame()["claim_id"])]

    def missing_claim_ids(self, claim_ids: list[str]) -> list[str]:
        """Unknown or out-of-scope: the caller can't tell which."""
        visible = set(self.claims_frame(claim_ids)["claim_id"])
        return [claim_id for claim_id in claim_ids if claim_id not in visible]

    def add_claim(self, fields: dict, lines: list[dict]) -> ClaimDetail:
        if not self.scope.allows(fields["facility_id"], fields["department_id"], fields["provider_id"]):
            raise OutOfScopeError("That provider, department, and facility are outside your access")
        return self.base.add_claim(fields, lines)

    def update_claim(self, fields: dict, lines: list[dict]) -> ClaimDetail:
        """Both the claim as it is and as edited must be inside the account's access."""
        self._require(fields["claim_id"])
        if not self.scope.allows(fields["facility_id"], fields["department_id"], fields["provider_id"]):
            raise OutOfScopeError("That provider, department, and facility are outside your access")
        return self.base.update_claim(fields, lines)

    def submission_frame(self, claim_id: str) -> pd.DataFrame:
        self._require(claim_id)
        return self.base.submission_frame(claim_id)

    def submit_claim(self, claim_id: str, edi: tuple[str, EdiFile] | None = None) -> ClaimDetail:
        self._require(claim_id)
        return self.base.submit_claim(claim_id, edi=edi)

    def apply_overrides(self, overrides: dict[str, dict[str, str]]) -> None:
        """Re-layer the organisation's corrections. `overrides` is always the whole
        correction store (it replaces the overlay), so it holds other people's claims too;
        what this person may correct is checked when the correction is added (AI Fix looks
        the claim up through this scoped view first)."""
        self.base.apply_overrides(overrides)

    def edi_text(self, claim_id: str) -> str | None:
        return self.base.edi_text(claim_id) if self._visible(self.base.get_claim(claim_id)) else None

    def next_control_number(self) -> int:
        return self.base.next_control_number()

    # --- Reference data: what a new claim may use ------------------------------

    def list_payers(self) -> list[Payer]:
        return self.base.list_payers()

    def get_payer(self, payer_id: str) -> Payer | None:
        return self.base.get_payer(payer_id)

    def list_providers(self) -> list[Provider]:
        """Providers whose claims the account could enter and see."""
        providers = self.base.list_providers()
        if not self.scope.restricted or self.scope.facilities:
            return providers  # at an in-scope facility, any provider will do
        return [
            p for p in providers
            if p.provider_id in self.scope.providers or p.department_id in self.scope.departments
        ]

    def get_provider(self, provider_id: str) -> Provider | None:
        return self.base.get_provider(provider_id)

    def list_departments(self) -> list[Department]:
        departments = self.base.list_departments()
        if not self.scope.restricted or self.scope.facilities:
            return departments
        reachable = set(self.scope.departments) | {
            p.department_id for p in self.base.list_providers() if p.provider_id in self.scope.providers
        }
        return [d for d in departments if d.department_id in reachable]

    def list_facilities(self) -> list[Facility]:
        facilities = self.base.list_facilities()
        if not self.scope.restricted or self.scope.departments or self.scope.providers:
            return facilities  # an in-scope department or provider can work anywhere
        return [f for f in facilities if f.facility_id in self.scope.facilities]

    def get_facility(self, facility_id: str) -> Facility | None:
        return self.base.get_facility(facility_id)

    # --- Patients: the register is organisation-wide, their history isn't ------

    def list_patients(self, query: PatientQuery) -> Page[PatientSummary]:
        page = self.base.list_patients(query)
        if self.scope.restricted:
            page = page.model_copy(update={"items": [self._scoped_counts(p) for p in page.items]})
        return page

    def get_patient(self, patient_id: str) -> PatientSummary | None:
        patient = self.base.get_patient(patient_id)
        return self._scoped_counts(patient) if patient and self.scope.restricted else patient

    def _scoped_counts(self, patient: PatientSummary) -> PatientSummary:
        claims = self.claims_frame()
        mine = claims[claims["patient_id"] == patient.patient_id]["claim_id"]
        denials = self.base.denials_frame()
        return patient.model_copy(update={
            "claim_count": len(mine),
            "denial_count": int(denials["claim_id"].isin(mine).sum()),
        })

    def person_names(self) -> list[tuple[str, str]]:
        return self.base.person_names()
