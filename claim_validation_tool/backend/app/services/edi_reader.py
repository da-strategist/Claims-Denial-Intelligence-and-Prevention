"""Reads a saved 837 back into named fields, so the PDFs show exactly what was sent.

Handles the files edi837.build_837 writes: one claim per interchange, 837P or 837I.
"""

from dataclasses import dataclass, field
from datetime import datetime

FILING_CODES = {
    "MB": "Medicare Part B",
    "16": "Medicare Advantage (HMO Medicare risk)",
    "MC": "Medicaid",
    "CI": "Commercial insurance",
    "CH": "TRICARE (CHAMPUS)",
    "WC": "Workers' compensation",
    "ZZ": "Mutually defined",
}
RELATIONSHIPS = {"18": "Self", "01": "Spouse", "19": "Child", "G8": "Other"}
RESPONSIBILITY = {"P": "Primary", "S": "Secondary", "T": "Tertiary"}


@dataclass
class Party:
    name: str = ""
    first_name: str = ""
    id: str = ""
    address: list[str] = field(default_factory=list)
    city: str = ""
    state: str = ""
    zip_code: str = ""
    birth_date: str = ""
    sex: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.name}, {self.first_name}" if self.first_name else self.name

    @property
    def city_line(self) -> str:
        zip_code = f"{self.zip_code[:5]}-{self.zip_code[5:]}" if len(self.zip_code) == 9 else self.zip_code
        return " ".join(part for part in (f"{self.city}," if self.city else "", self.state, zip_code) if part)


@dataclass
class Policy:
    responsibility: str = "P"
    relationship: str = "18"
    group_number: str = ""
    filing_code: str = ""
    holder: Party = field(default_factory=Party)
    payer: Party = field(default_factory=Party)


@dataclass
class Line:
    number: int
    procedure: str
    modifiers: list[str]
    charge: str
    units: str
    revenue_code: str = ""
    pointer: str = ""
    service_date: str = ""


@dataclass
class Claim837:
    transaction: str = ""
    version: str = ""
    test: bool = True
    control_number: str = ""
    created: str = ""
    sender_id: str = ""
    receiver_id: str = ""
    submitter: Party = field(default_factory=Party)
    submitter_contact: str = ""
    submitter_phone: str = ""
    receiver: Party = field(default_factory=Party)
    billing: Party = field(default_factory=Party)
    billing_tax_id: str = ""
    policy: Policy = field(default_factory=Policy)
    patient: Party | None = None  # only when the patient isn't the policy holder
    claim_id: str = ""
    total_charge: str = ""
    place_or_bill: str = ""  # place of service (837P) or facility type + frequency (837I)
    frequency: str = ""
    prior_auth: str = ""
    statement_period: str = ""
    admission_type: str = ""
    admission_source: str = ""
    patient_status: str = ""
    diagnoses: list[str] = field(default_factory=list)
    provider: Party = field(default_factory=Party)  # rendering (837P) or attending (837I)
    facility: Party = field(default_factory=Party)
    other_policies: list[Policy] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
    segments: list[str] = field(default_factory=list)

    @property
    def institutional(self) -> bool:
        return self.transaction == "837I"

    @property
    def patient_party(self) -> Party:
        """The patient: their own loop, or the policy holder when that's them."""
        return self.patient or self.policy.holder


def _date(ccyymmdd: str) -> str:
    try:
        return datetime.strptime(ccyymmdd, "%Y%m%d").date().isoformat()
    except ValueError:
        return ccyymmdd


def _dx(code: str) -> str:
    return f"{code[:3]}.{code[3:]}" if len(code) > 3 else code


def _get(elements: list[str], index: int) -> str:
    return elements[index] if index < len(elements) else ""


def read_837(text: str) -> Claim837:
    claim = Claim837()
    claim.segments = [s.strip() for s in text.split("~") if s.strip()]
    current: Party | None = None
    in_other = False
    line: Line | None = None

    for segment in claim.segments:
        e = segment.split("*")
        tag = e[0]
        if tag == "ISA":
            claim.sender_id, claim.receiver_id = _get(e, 6).strip(), _get(e, 8).strip()
            claim.test = _get(e, 15) == "T"
            claim.control_number = _get(e, 13)
            claim.created = datetime.strptime(_get(e, 9) + _get(e, 10), "%y%m%d%H%M").strftime("%Y-%m-%d %H:%M")
        elif tag == "GS":
            claim.version = _get(e, 8)
            claim.transaction = "837I" if claim.version.endswith("X223A2") else "837P"
        elif tag == "NM1":
            entity = _get(e, 1)
            party = Party(name=_get(e, 3), first_name=_get(e, 4), id=_get(e, 9))
            if entity == "41":
                claim.submitter = party
            elif entity == "40":
                claim.receiver = party
            elif entity == "85":
                claim.billing = party
            elif entity == "IL":
                if in_other:
                    claim.other_policies[-1].holder = party
                else:
                    claim.policy.holder = party
            elif entity == "PR":
                if in_other:
                    claim.other_policies[-1].payer = party
                else:
                    claim.policy.payer = party
            elif entity == "QC":
                claim.patient = party
            elif entity in ("82", "71"):
                claim.provider = party
            elif entity == "77":
                claim.facility = party
            current = party
        elif tag == "PER" and _get(e, 1) == "IC":
            claim.submitter_contact, claim.submitter_phone = _get(e, 2), _get(e, 4)
        elif tag == "N3" and current is not None:
            current.address = [part for part in e[1:] if part]
        elif tag == "N4" and current is not None:
            current.city, current.state, current.zip_code = _get(e, 1), _get(e, 2), _get(e, 3)
        elif tag == "DMG" and current is not None:
            current.birth_date, current.sex = _date(_get(e, 2)), _get(e, 3)
        elif tag == "REF":
            if _get(e, 1) == "EI":
                claim.billing_tax_id = _get(e, 2)
            elif _get(e, 1) == "G1":
                claim.prior_auth = _get(e, 2)
        elif tag == "SBR":
            policy = Policy(
                responsibility=_get(e, 1),
                relationship=_get(e, 2),
                group_number=_get(e, 3),
                filing_code=_get(e, 9),
            )
            if claim.claim_id:  # after CLM: other coverage (2320)
                in_other = True
                claim.other_policies.append(policy)
            else:
                claim.policy = policy
        elif tag == "PAT":
            claim.policy.relationship = _get(e, 1)
        elif tag == "CLM":
            claim.claim_id, claim.total_charge = _get(e, 1), _get(e, 2)
            parts = _get(e, 5).split(":")
            claim.place_or_bill = parts[0]
            claim.frequency = parts[2] if len(parts) > 2 else ""
        elif tag == "DTP":
            qualifier = _get(e, 1)
            if qualifier == "434":
                start, _, end = _get(e, 3).partition("-")
                claim.statement_period = f"{_date(start)} – {_date(end)}"
            elif qualifier == "472" and line is not None:
                line.service_date = _date(_get(e, 3))
        elif tag == "CL1":
            claim.admission_type, claim.admission_source, claim.patient_status = _get(e, 1), _get(e, 2), _get(e, 3)
        elif tag == "HI":
            claim.diagnoses += [_dx(item.split(":")[1]) for item in e[1:] if ":" in item]
        elif tag == "LX":
            line = Line(number=int(_get(e, 1)), procedure="", modifiers=[], charge="", units="")
            claim.lines.append(line)
        elif tag in ("SV1", "SV2") and line is not None:
            procedure_at, charge_at, units_at = (1, 2, 4) if tag == "SV1" else (2, 3, 5)
            procedure = _get(e, procedure_at).split(":")
            line.procedure, line.modifiers = _get(procedure, 1), procedure[2:]
            line.charge, line.units = _get(e, charge_at), _get(e, units_at)
            if tag == "SV1":
                line.pointer = _get(e, 7)
            else:
                line.revenue_code = _get(e, 1)
    return claim
