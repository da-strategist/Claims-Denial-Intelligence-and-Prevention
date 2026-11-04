"""Keeping the patient list up to date from the claims hospitals send.

A patient on a claim is registered with the hospital, so a claim is never refused for being
someone we haven't seen. A clear match updates that patient; no match adds them; an unclear
match adds them too, flagged for a person to look at, and is never merged automatically,
because mixing up two people's records is worse than having a duplicate.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from threading import Lock

from fastapi import HTTPException

from app.models import PatientQuery, Sex
from app.services.assistant import get_name_scrubber

# Stands in for the patient's ID on a claim that's been read, until it's saved
UNRESOLVED_PATIENT = "PAT000000"


@dataclass
class IncomingPatient:
    """The patient as a claim describes them."""

    first_name: str
    last_name: str
    birth_date: date | None
    payer_id: str
    member_id: str = ""
    sex: str = ""
    zip_code: str = ""
    # Only when the claim says which payer is primary
    primary_payer_id: str | None = None


@dataclass
class ResolvedPatient:
    patient_id: str
    added: bool = False
    review: list[str] = field(default_factory=list)
    undo: Callable[[], None] = lambda: None

    def notes(self) -> list[str]:
        notes = ["New patient: added to your patient list from this claim."] if self.added else []
        if self.review:
            notes.append(
                f"This patient may already be on your list as {', '.join(self.review)}. "
                "They were kept separate for someone to check."
            )
        return notes


@lru_cache(maxsize=None)
def save_lock(org_id: str) -> Lock:
    """One claim saved at a time, so two claims can't add the same patient or claim number."""
    return Lock()


def _same(a: str, b: str) -> bool:
    return a.strip().casefold() == b.strip().casefold()


def find_patient(incoming: IncomingPatient, repo, registrations, today: date):
    """(the patient who clearly matches or None, IDs of patients who might be them)."""
    named = repo.list_patients(
        PatientQuery(search=f"{incoming.first_name} {incoming.last_name}", page_size=50)
    ).items
    named = [
        p for p in named if _same(p.first_name, incoming.first_name) and _same(p.last_name, incoming.last_name)
    ]

    def policy_matches(patient) -> bool:
        registration = _registration(patient, repo, registrations, today)
        policy = registration.policies.get(incoming.payer_id)
        return bool(incoming.member_id) and policy is not None and policy.member_id == incoming.member_id

    if incoming.birth_date is None:
        clear = [p for p in named if policy_matches(p)]
    else:
        clear = [
            p for p in named
            if _registration(p, repo, registrations, today).birth_date == incoming.birth_date
        ]
        if len(clear) > 1:  # same name and birthday: the member ID tells them apart, if it can
            clear = [p for p in clear if policy_matches(p)] or clear
    if len(clear) == 1:
        return clear[0], []

    near = {p.patient_id for p in named}
    if incoming.member_id:
        near |= set(registrations.with_policy(incoming.payer_id, incoming.member_id))
    if incoming.birth_date is not None:
        for patient_id in registrations.born_on(incoming.birth_date):
            patient = repo.get_patient(patient_id)
            if patient and (_same(patient.first_name, incoming.first_name) or _same(patient.last_name, incoming.last_name)):
                near.add(patient_id)
    return None, sorted(near)


def _registration(patient, repo, registrations, today: date):
    return registrations.get(patient, repo.get_payer(patient.primary_payer_id), today)


def _age(birth_date: date, today: date) -> int:
    before_birthday = (today.month, today.day) < (birth_date.month, birth_date.day)
    return max(0, today.year - birth_date.year - before_birthday)


def _changes(patient, incoming: IncomingPatient, today: date) -> dict:
    """What this claim says that the list doesn't. Only what the claim actually states."""
    changes = {}
    if incoming.zip_code and incoming.zip_code != patient.zip_code:
        changes["zip_code"] = incoming.zip_code
    if incoming.sex in (Sex.FEMALE, Sex.MALE) and incoming.sex != patient.gender:
        changes["gender"] = incoming.sex
    if incoming.primary_payer_id and incoming.primary_payer_id != patient.primary_payer_id:
        changes["primary_payer_id"] = incoming.primary_payer_id
    if incoming.birth_date is not None and _age(incoming.birth_date, today) != patient.age:
        changes["age"] = _age(incoming.birth_date, today)
    return changes


def update_known(patient, incoming: IncomingPatient, repo, today: date, rename: bool = False) -> ResolvedPatient:
    """Bring a patient up to date with this claim. `undo` puts them back if it can't be saved."""
    changes = _changes(patient, incoming, today)
    if rename and not (_same(patient.first_name, incoming.first_name) and _same(patient.last_name, incoming.last_name)):
        changes.update(first_name=incoming.first_name, last_name=incoming.last_name)
        get_name_scrubber.cache_clear()  # the assistant must mask the new spelling too
    undo = repo.update_patient(patient.patient_id, changes) if changes else (lambda: None)
    return ResolvedPatient(patient.patient_id, undo=undo)


def resolve_patient(incoming: IncomingPatient, repo, registrations, today: date, by: str) -> ResolvedPatient:
    """The patient a claim is for: matched and updated, or added. Hold save_lock throughout,
    and call `undo` if the claim then can't be saved, so no one is listed without a claim."""
    patient, near = find_patient(incoming, repo, registrations, today)
    if patient is not None:
        return update_known(patient, incoming, repo, today)
    if incoming.birth_date is None:
        raise HTTPException(
            status_code=422,
            detail="This patient isn't on your list yet, so the claim needs their date of birth",
        )
    sex = incoming.sex if incoming.sex in (Sex.FEMALE, Sex.MALE) else Sex.UNKNOWN
    patient_id = repo.add_patient(
        {
            "first_name": incoming.first_name.strip(),
            "last_name": incoming.last_name.strip(),
            "age": _age(incoming.birth_date, today),
            "gender": sex.value if isinstance(sex, Sex) else sex,
            "primary_payer_id": incoming.primary_payer_id or incoming.payer_id,
            "zip_code": incoming.zip_code,
        },
        by,
        near,
    )
    # New names must be masked before any question goes to the assistant's model
    get_name_scrubber.cache_clear()

    def undo() -> None:
        repo.remove_patient(patient_id)
        get_name_scrubber.cache_clear()

    return ResolvedPatient(patient_id, added=True, review=near, undo=undo)
