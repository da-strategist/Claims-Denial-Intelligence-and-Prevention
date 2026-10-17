"""Builds the X12 837 claim file a claim is submitted with.

837P (005010X222A1) for professional claims, 837I (005010X223A2) for institutional ones,
one claim per interchange. Segments end with "~", elements are separated by "*", and
components by ":". Free text is upper-cased and stripped of those separators.

The file is built from the claim, its billing details (captured at entry), the payers,
provider, and facility, and the organisation's EDI settings. Missing settings are filled
with NOTSET and the file is marked as a test file (ISA15 = T), with notes saying why.
"""

from dataclasses import dataclass
from datetime import datetime

from app.models import (
    RELATIONSHIP_CODES,
    ClaimDetail,
    ClaimType,
    EdiFile,
    Facility,
    Payer,
    PolicyHolder,
    Relationship,
)
from app.services.edi_settings import EdiSettings

NOT_SET = "NOTSET"

VERSION = {ClaimType.PROFESSIONAL: "005010X222A1", ClaimType.INSTITUTIONAL: "005010X223A2"}
TRANSACTION = {ClaimType.PROFESSIONAL: "837P", ClaimType.INSTITUTIONAL: "837I"}

# SBR09: the kind of insurance, by payer type
CLAIM_FILING_CODES = {
    "Medicare": "MB",
    "Medicare Advantage": "16",
    "Medicaid": "MC",
    "Medicaid MCO": "MC",
    "Commercial": "CI",
    "Government": "CH",
    "Workers Comp": "WC",
}
RESPONSIBILITY = ["P", "S", "T"]  # primary, secondary, tertiary


@dataclass
class ClaimParties:
    """Everything the 837 names besides the claim itself."""

    payers: list[Payer]  # billed payer first, then other coverage in order
    facility: Facility
    settings: EdiSettings


def _clean(value: object) -> str:
    text = str(value).upper()
    for separator in "*~:^":
        text = text.replace(separator, " ")
    return " ".join(text.split())


def _or_not_set(value: str) -> str:
    return _clean(value) if value else NOT_SET


def _amount(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def _dx(code: str) -> str:
    return code.replace(".", "")


def _split_name(full_name: str, credential: str = "") -> tuple[str, str]:
    """("Carol", "Robinson") from "Dr. Carol Robinson"."""
    words = [w for w in full_name.split() if w.rstrip(".") not in ("Dr", credential)]
    return (" ".join(words[:-1]) or words[0], words[-1]) if words else ("", "")


def _split_address(one_line: str) -> tuple[str, str, str, str]:
    """("4200 Providence Rd", "Charlotte", "NC", "28211") from the facility's address."""
    parts = [p.strip() for p in one_line.split(",")]
    if len(parts) >= 3 and len(parts[-1].split()) == 2:
        state, zip_code = parts[-1].split()
        return ", ".join(parts[:-2]), parts[-2], state, zip_code
    return one_line, "", "", ""


class _Segments:
    def __init__(self) -> None:
        self.items: list[str] = []

    def add(self, *elements: object) -> None:
        values = ["" if e is None else str(e) for e in elements]
        while values and values[-1] == "":  # trailing empty elements are left off
            values.pop()
        self.items.append("*".join(values))


def build_837(
    claim: ClaimDetail, parties: ClaimParties, control_number: int, now: datetime
) -> tuple[str, EdiFile]:
    """The 837 file for `claim` and a summary of it. Raises ValueError if the claim has
    no billing details (claims from the source data were never entered in the app)."""
    if claim.billing is None or claim.patient is None or claim.provider is None:
        raise ValueError(f"{claim.claim_id} has no billing details to build an 837 from")
    billing = claim.billing
    settings = parties.settings
    institutional = claim.claim_type == ClaimType.INSTITUTIONAL
    version = VERSION[claim.claim_type]
    payer_ids = [p.payer_id for p in parties.payers]
    notes = settings.missing(payer_ids)
    # 5010 wants ZIP+4 wherever the service was performed
    facility_zip = _split_address(parties.facility.address)[3]
    if not (facility_zip.isdigit() and len(facility_zip) == 9):
        notes.append(f"ZIP+4 (9 digits) for {parties.facility.facility_name}")
    test = settings.mode != "production" or bool(notes)
    control = f"{control_number:09d}"
    sender = _or_not_set(settings.submitter.id)
    receiver = _or_not_set(settings.receiver.id)

    s = _Segments()
    s.add(
        "ISA", "00", " " * 10, "00", " " * 10, "ZZ", sender.ljust(15)[:15], "ZZ",
        receiver.ljust(15)[:15], now.strftime("%y%m%d"), now.strftime("%H%M"), "^", "00501",
        control, "0", "T" if test else "P", ":",
    )
    s.add("GS", "HC", sender, receiver, now.strftime("%Y%m%d"), now.strftime("%H%M"), control_number, "X", version)
    first_transaction_segment = len(s.items)
    s.add("ST", "837", "0001", version)
    s.add("BHT", "0019", "00", claim.claim_id, now.strftime("%Y%m%d"), now.strftime("%H%M"), "CH")

    # 1000A submitter, 1000B receiver
    s.add("NM1", "41", "2", _or_not_set(settings.submitter.name), "", "", "", "", "46", sender)
    s.add("PER", "IC", _or_not_set(settings.submitter.contact_name), "TE", _or_not_set(settings.submitter.phone))
    s.add("NM1", "40", "2", _or_not_set(settings.receiver.name), "", "", "", "", "46", receiver)

    # 2000A / 2010AA billing provider: the organisation, else the facility's own details
    provider = settings.billing_provider
    fac_line1, fac_city, fac_state, fac_zip = _split_address(parties.facility.address)
    s.add("HL", "1", "", "20", "1")
    s.add("NM1", "85", "2", _clean(provider.name or parties.facility.facility_name), "", "", "", "", "XX", _or_not_set(provider.npi))
    if provider.address.line1:
        address = provider.address
        s.add("N3", _clean(address.line1))
        s.add("N4", _clean(address.city), _clean(address.state), address.zip_code)
    else:
        s.add("N3", _clean(fac_line1))
        s.add("N4", _clean(fac_city), _clean(fac_state), fac_zip)
    s.add("REF", "EI", _or_not_set(provider.tax_id))

    # 2000B / 2010BA subscriber, 2010BB payer
    patient = claim.patient
    policy = billing.policy
    is_self = policy is None or policy.relationship == Relationship.SELF
    payer = parties.payers[0]
    s.add("HL", "2", "1", "22", "0" if is_self else "1")
    s.add(
        "SBR", "P", "18" if is_self else "", _clean(policy.group_number) if policy and policy.group_number else "",
        "", "", "", "", "", CLAIM_FILING_CODES.get(payer.payer_type, "ZZ"),
    )
    holder_last, holder_first = _holder_name(policy, patient)
    s.add("NM1", "IL", "1", holder_last, holder_first, "", "", "", "MI", _clean(policy.member_id) if policy else NOT_SET)
    if is_self:
        _address_and_demographics(s, billing.patient_address, billing.patient_birth_date, patient.gender)
    s.add("NM1", "PR", "2", _clean(payer.payer_name), "", "", "", "", "PI", _payer_id(settings, payer))

    # 2000C / 2010CA patient, when the patient isn't the policy holder
    if not is_self:
        s.add("HL", "3", "2", "23", "0")
        s.add("PAT", RELATIONSHIP_CODES[policy.relationship])
        s.add("NM1", "QC", "1", _clean(patient.last_name), _clean(patient.first_name))
        _address_and_demographics(s, billing.patient_address, billing.patient_birth_date, patient.gender)

    # 2300 claim
    service = claim.service_date.strftime("%Y%m%d")
    total = _amount(sum(line.charge_amount for line in claim.lines))
    diagnoses = [claim.primary_icd10, *claim.additional_icd10]
    if institutional:
        details = billing.institutional
        bill = details.type_of_bill
        s.add("CLM", claim.claim_id, total, "", "", f"{bill[:2]}:A:{bill[2]}", "", "A", "Y", "Y")
        s.add("DTP", "434", "RD8", f"{service}-{service}")
        s.add("CL1", details.admission_type, details.admission_source, details.patient_status)
    else:
        s.add("CLM", claim.claim_id, total, "", "", f"{claim.place_of_service}:B:1", "Y", "A", "Y", "Y")
    if claim.pa_number:
        s.add("REF", "G1", _clean(claim.pa_number))
    s.add("HI", *[f"{'ABK' if i == 0 else 'ABF'}:{_dx(code)}" for i, code in enumerate(diagnoses)])

    # 2310 providers: rendering (professional) or attending (institutional), and the facility
    first, last = _split_name(claim.provider.provider_name, claim.provider.credential)
    s.add("NM1", "71" if institutional else "82", "1", _clean(last), _clean(first), "", "", "", "XX", claim.provider.npi)
    s.add("NM1", "77", "2", _clean(parties.facility.facility_name))
    s.add("N3", _clean(fac_line1))
    s.add("N4", _clean(fac_city), _clean(fac_state), fac_zip)

    # 2320 / 2330 other coverage
    for index, (other_payer, other_policy) in enumerate(
        zip(parties.payers[1:], billing.other_policies), start=1
    ):
        other_self = other_policy.relationship == Relationship.SELF
        s.add(
            "SBR", RESPONSIBILITY[index], RELATIONSHIP_CODES[other_policy.relationship],
            _clean(other_policy.group_number or ""), "", "", "", "", "",
            CLAIM_FILING_CODES.get(other_payer.payer_type, "ZZ"),
        )
        s.add("OI", "", "", "Y", "" if institutional else "P", "", "Y")
        other_last, other_first = _holder_name(other_policy, patient) if not other_self else (
            _clean(patient.last_name), _clean(patient.first_name),
        )
        s.add("NM1", "IL", "1", other_last, other_first, "", "", "", "MI", _clean(other_policy.member_id))
        s.add("NM1", "PR", "2", _clean(other_payer.payer_name), "", "", "", "", "PI", _payer_id(settings, other_payer))

    # 2400 service lines
    for number, line in enumerate(claim.lines, start=1):
        procedure = ":".join(["HC", line.cpt_code, *([line.modifier] if line.modifier else [])])
        s.add("LX", number)
        if institutional:
            s.add("SV2", line.revenue_code, procedure, _amount(line.charge_amount), "UN", line.units)
        else:
            pointer = diagnoses.index(line.icd10_pointer) + 1
            s.add("SV1", procedure, _amount(line.charge_amount), "UN", line.units, "", "", pointer)
        s.add("DTP", "472", "D8", service)

    segment_count = len(s.items) - first_transaction_segment + 1  # ST through SE
    s.add("SE", segment_count, "0001")
    s.add("GE", "1", control_number)
    s.add("IEA", "1", control)

    summary = EdiFile(
        transaction=TRANSACTION[claim.claim_type],
        control_number=control,
        generated_at=now.isoformat(),
        test=test,
        notes=(
            [f"Not set: {', '.join(notes)}"] if notes else []
        ) + ([] if settings.mode == "production" else ["Settings mode is test"]),
    )
    return "~\n".join(s.items) + "~\n", summary


def _payer_id(settings: EdiSettings, payer: Payer) -> str:
    return _clean(settings.payer_ids.get(payer.payer_id) or payer.payer_id)


def _holder_name(policy: PolicyHolder | None, patient) -> tuple[str, str]:
    if policy is None or policy.relationship == Relationship.SELF:
        return _clean(patient.last_name), _clean(patient.first_name)
    return _clean(policy.last_name), _clean(policy.first_name)


def _address_and_demographics(s: _Segments, address, birth_date, sex: str) -> None:
    lines = [_clean(address.line1)] + ([_clean(address.line2)] if address.line2 else [])
    s.add("N3", *lines)
    s.add("N4", _clean(address.city), address.state, address.zip_code)
    s.add("DMG", "D8", birth_date.strftime("%Y%m%d"), sex if sex in ("F", "M") else "U")
