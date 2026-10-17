"""Patients' billing details (date of birth, address, insurance policies), kept apart from
the source registry, which only has name, age, sex, ZIP code, and primary payer.

Two sources, entered first:
- entered: captured from a claim (New Claim form or API) and saved here, readable only by
  this account. A patient's next claim is filled in from it.
- sample: generated for the synthetic sample patients so their claims can be filled in
  too. Generation is deterministic (seeded by patient ID), consistent with the registry
  (the date of birth matches the age, the address is in the patient's ZIP code), and
  marked as sample data. Nothing generated is ever written to disk.
"""

import hashlib
import json
import os
import random
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from threading import Lock

from app.models import (
    Address,
    ClaimBilling,
    Patient,
    PatientRegistration,
    Payer,
    PolicyHolder,
    RegistrationSource,
    Sex,
)

DEFAULT_REGISTRATIONS_FILE = Path(__file__).resolve().parents[2] / "patient_registrations.json"

# Every sample patient lives in a Charlotte ZIP code (282xx)
_SAMPLE_CITIES = {"282": ("Charlotte", "NC")}
_SAMPLE_STREETS = [
    "Providence Rd", "Sharon Amity Rd", "Park Rd", "Central Ave", "Beatties Ford Rd",
    "Monroe Rd", "Albemarle Rd", "Tryon St", "Selwyn Ave", "Queens Rd", "Sugar Creek Rd",
    "Freedom Dr", "Wilkinson Blvd", "Fairview Rd", "Rea Rd", "Mallard Creek Rd",
]
# Payers whose members usually belong to an employer group
_GROUP_PAYER_TYPES = {"Commercial", "Medicare Advantage", "Workers Comp"}


def _rng(patient_id: str) -> random.Random:
    seed = int.from_bytes(hashlib.sha256(patient_id.encode()).digest()[:8], "big")
    return random.Random(seed)


def sample_registration(patient: Patient, payer: Payer | None, today: date) -> PatientRegistration:
    """Plausible billing details for a synthetic sample patient (same every time)."""
    rng = _rng(patient.patient_id)
    # Born between `age + 1` years ago (exclusive) and `age` years ago, so the age matches
    latest = _years_before(today, patient.age)
    earliest = _years_before(today, patient.age + 1) + timedelta(days=1)
    birth_date = earliest + timedelta(days=rng.randrange((latest - earliest).days + 1))
    city, state = _SAMPLE_CITIES.get(patient.zip_code[:3], ("Charlotte", "NC"))
    policies = {}
    if payer is not None and payer.payer_type != "Self-Pay":
        prefix = (payer.policy_prefix or payer.payer_id).replace("-", "")
        policies[payer.payer_id] = PolicyHolder(
            member_id=f"{prefix}{rng.randrange(10**8, 10**9)}",
            group_number=f"GRP{rng.randrange(10**4, 10**5)}" if payer.payer_type in _GROUP_PAYER_TYPES else None,
        )
    return PatientRegistration(
        patient_id=patient.patient_id,
        birth_date=birth_date,
        sex=Sex(patient.gender) if patient.gender in Sex._value2member_map_ else Sex.UNKNOWN,
        address=Address(
            line1=f"{rng.randrange(100, 9900)} {rng.choice(_SAMPLE_STREETS)}",
            city=city,
            state=state,
            zip_code=patient.zip_code,
        ),
        policies=policies,
        source=RegistrationSource.SAMPLE,
    )


def _years_before(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:  # 29 February
        return day.replace(year=day.year - years, day=28)


class RegistrationStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._entered: dict[str, PatientRegistration] = {}
        self._lock = Lock()
        if path is not None and path.exists():
            for item in json.loads(path.read_text())["registrations"]:
                registration = PatientRegistration.model_validate(item)
                self._entered[registration.patient_id] = registration

    def get(self, patient: Patient, payer: Payer | None, today: date) -> PatientRegistration:
        """The entered details if there are any, else sample details."""
        with self._lock:
            entered = self._entered.get(patient.patient_id)
        return entered or sample_registration(patient, payer, today)

    def record_claim(
        self,
        patient: Patient,
        sex: Sex,
        billing: ClaimBilling,
        payer_ids: list[str],
        username: str,
    ) -> PatientRegistration:
        """Save what a claim captured, so the patient's next claim starts from it.

        Policies are kept per payer: this claim's policies replace those payers' earlier
        details, and policies for other payers are kept.
        """
        with self._lock:
            earlier = self._entered.get(patient.patient_id)
            policies = dict(earlier.policies) if earlier else {}
            for payer_id, policy in zip(payer_ids, [billing.policy, *billing.other_policies]):
                if policy is not None:
                    policies[payer_id] = policy
            registration = PatientRegistration(
                patient_id=patient.patient_id,
                birth_date=billing.patient_birth_date,
                sex=sex,
                address=billing.patient_address,
                policies=policies,
                source=RegistrationSource.ENTERED,
                updated_at=datetime.now(UTC).isoformat(),
                updated_by=username,
            )
            self._entered[patient.patient_id] = registration
            self._save()
            return registration

    def _save(self) -> None:
        """Write every entered registration atomically, owner-only. Caller holds the lock."""
        if self.path is None:
            return
        payload = {"registrations": [r.model_dump(mode="json") for r in self._entered.values()]}
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(payload, indent=2))
        tmp.replace(self.path)


@lru_cache(maxsize=1)
def get_registration_store() -> RegistrationStore:
    """Process-wide store saved to RCM_REGISTRATIONS_FILE."""
    return RegistrationStore(
        Path(os.environ.get("RCM_REGISTRATIONS_FILE", DEFAULT_REGISTRATIONS_FILE))
    )
