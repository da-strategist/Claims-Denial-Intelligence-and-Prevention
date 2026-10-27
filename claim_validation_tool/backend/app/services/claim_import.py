"""Reads an uploaded claims file into New Claim requests (ClaimCreate bodies).

Two kinds of file:

- CSV or Excel in the template's layout: one row per service line, rows grouped into
  claims by claim_ref. Billing details left blank come from the patient's registration,
  as the New Claim form fills them in.
- X12 837P / 837I, from this app or another billing system: any number of claims. The
  patient is matched by name and date of birth (or member ID), the payer by its ID or
  name, the provider by NPI and the facility by name.

Nothing here saves anything: each claim comes back as a request body to create, or as
the reasons it couldn't be read.
"""

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime

import pandas as pd
from pydantic import ValidationError

from app.models import ClaimCreate, PatientQuery, PayerType
from app.models.billing import RELATIONSHIP_CODES, Relationship
from app.models.claim import PlaceOfService
from app.services.edi_reader import Claim837, Party, Policy, read_837

# The template: required columns first, then optional ones
REQUIRED_COLUMNS = (
    "claim_ref", "patient_id", "payer_id", "provider_id", "service_date", "diagnoses", "cpt_code",
)
OPTIONAL_COLUMNS = (
    "icd10_pointer", "units", "modifier", "charge_amount", "revenue_code",
    "facility_id", "claim_type", "place_of_service", "submission_date",
    "pa_required", "pa_obtained", "pa_number", "other_payer_ids",
    "member_id", "group_number", "other_member_ids",
    "patient_birth_date", "address_line1", "address_line2", "city", "state", "zip_code",
    "type_of_bill", "admission_type", "admission_source", "patient_status",
)
LINE_COLUMNS = ("cpt_code", "icd10_pointer", "units", "modifier", "charge_amount", "revenue_code")
HEADER_COLUMNS = tuple(c for c in REQUIRED_COLUMNS + OPTIONAL_COLUMNS if c not in LINE_COLUMNS)

TEMPLATE_ROWS = [
    {
        "claim_ref": "A1", "patient_id": "PAT000003", "payer_id": "PAY001", "provider_id": "PROV001",
        "service_date": "2026-01-05", "diagnoses": "E11.65|I10", "cpt_code": "99213",
        "icd10_pointer": "E11.65", "units": "1",
    },
    {"claim_ref": "A1", "cpt_code": "99214", "icd10_pointer": "I10", "units": "1"},
]

_RELATIONSHIPS = {code: relationship for relationship, code in RELATIONSHIP_CODES.items()}
_DIAGNOSIS_QUALIFIERS = {"ABK", "ABF", "BK", "BF"}  # principal and other diagnoses
_TRUE, _FALSE = {"y", "yes", "true", "1"}, {"n", "no", "false", "0", ""}


class ImportFileError(ValueError):
    """The file as a whole can't be read (wrong layout, not a claims file)."""


@dataclass
class ParsedClaim:
    ref: str
    where: str
    body: ClaimCreate | None = None
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def template_csv() -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=[*REQUIRED_COLUMNS, *OPTIONAL_COLUMNS], lineterminator="\n")
    writer.writeheader()
    writer.writerows(TEMPLATE_ROWS)
    return out.getvalue()


def file_type(filename: str, data: bytes) -> str:
    """csv, xlsx or 837 (P or I is decided when it's read)."""
    if data[:4] == b"PK\x03\x04":
        return "xlsx"
    if data.lstrip()[:3] == b"ISA":
        return "837"
    if filename.lower().endswith((".csv", ".txt")):
        return "csv"
    raise ImportFileError("Upload a CSV or Excel file in the template's layout, or an X12 837 file")


# ----- CSV / Excel -----------------------------------------------------------------


def read_table(data: bytes, kind: str) -> pd.DataFrame:
    try:
        if kind == "xlsx":
            frame = pd.read_excel(io.BytesIO(data), dtype=str)
        else:
            frame = pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except Exception as err:  # noqa: BLE001 - any parser error means the same to the user
        raise ImportFileError(f"Couldn't read the file as a table: {err}") from err
    frame = frame.fillna("")
    frame.columns = [re.sub(r"\s+", "_", str(c).strip().lower()) for c in frame.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ImportFileError(
            f"The file is missing the column{'s' if len(missing) > 1 else ''} {', '.join(missing)}. "
            "Download the template to see the layout."
        )
    for column in OPTIONAL_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    frame = frame.apply(lambda col: col.astype(str).str.strip())
    # Rows with nothing in them (common at the end of spreadsheets) aren't claims
    return frame[(frame != "").any(axis=1)]


def parse_table(frame: pd.DataFrame, repo, registrations, today: date) -> list[ParsedClaim]:
    claims: list[ParsedClaim] = []
    frame = frame.assign(_row=frame.index + 2)  # the spreadsheet's row number (1 is headers)
    blank = frame[frame["claim_ref"] == ""]
    for row in blank["_row"]:
        claims.append(ParsedClaim(ref="", where=f"row {row}", errors=["claim_ref is blank"]))
    groups = frame[frame["claim_ref"] != ""].groupby("claim_ref", sort=False)
    for ref, rows in groups:
        numbers = list(rows["_row"])
        where = f"row {numbers[0]}" if len(numbers) == 1 else f"rows {', '.join(map(str, numbers))}"
        claim = ParsedClaim(ref=str(ref), where=where)
        try:
            body = _table_claim(rows, repo, registrations, today, claim)
        except ValueError as err:
            claim.errors.append(str(err))
        else:
            _check(claim, body)
        claims.append(claim)
    return claims


def _table_claim(rows: pd.DataFrame, repo, registrations, today: date, claim: ParsedClaim) -> dict:
    header = {}
    for column in HEADER_COLUMNS:
        values = list(dict.fromkeys(v for v in rows[column] if v))
        if len(values) > 1:
            raise ValueError(f"The rows give different {column} values ({', '.join(values)}): use one per claim")
        header[column] = values[0] if values else ""

    diagnoses = [code.upper() for code in re.split(r"[|;,\s]+", header["diagnoses"]) if code]
    if not diagnoses:
        raise ValueError("diagnoses is blank: list the claim's diagnosis codes, primary first")
    service_date = _date(header["service_date"], "service_date")
    lines = []
    for _, row in rows.iterrows():
        if not row["cpt_code"]:
            raise ValueError(f"Row {row['_row']}: cpt_code is blank")
        lines.append(
            {
                "cpt_code": row["cpt_code"],
                "icd10_pointer": row["icd10_pointer"].upper() or diagnoses[0],
                "units": _number(row["units"], "units", int) if row["units"] else 1,
                "modifier": row["modifier"].upper() or None,
                "charge_amount": _number(row["charge_amount"], "charge_amount", float) if row["charge_amount"] else None,
                "revenue_code": row["revenue_code"] or None,
            }
        )

    payer_id = header["payer_id"].upper()
    other_payer_ids = [p.upper() for p in _split(header["other_payer_ids"])]
    patient = repo.get_patient(header["patient_id"].upper())
    if patient is None:
        raise ValueError(f"Patient {header['patient_id']} is not registered")
    registration = registrations.get(patient, repo.get_payer(patient.primary_payer_id), today)

    pa_number = header["pa_number"] or None
    pa_obtained = _bool(header["pa_obtained"], "pa_obtained") or bool(pa_number)
    institutional = None
    if any(header[c] for c in ("type_of_bill", "admission_type", "admission_source", "patient_status")):
        institutional = {
            c: header[c] for c in ("type_of_bill", "admission_type", "admission_source", "patient_status")
        }
    claim_type = header["claim_type"].capitalize() or ("Institutional" if institutional else "Professional")

    if header["address_line1"]:
        address = {
            "line1": header["address_line1"], "line2": header["address_line2"] or None,
            "city": header["city"], "state": header["state"].upper(), "zip_code": header["zip_code"],
        }
    else:
        address = registration.address.model_dump(mode="json")
    other_members = _split(header["other_member_ids"])
    other_policies = []
    for n, other_id in enumerate(other_payer_ids):
        if n < len(other_members):
            other_policies.append({"member_id": other_members[n]})
        elif other_id in registration.policies:
            other_policies.append(registration.policies[other_id].model_dump(mode="json"))
        else:
            raise ValueError(f"Give the member ID for other payer {other_id} (other_member_ids)")

    return {
        "patient_id": patient.patient_id,
        "payer_id": payer_id,
        "other_payer_ids": other_payer_ids,
        "provider_id": header["provider_id"].upper(),
        "facility_id": header["facility_id"].upper() or _default_facility(repo),
        "diagnoses": diagnoses,
        "lines": lines,
        "claim_type": claim_type,
        "place_of_service": header["place_of_service"] or PlaceOfService.OFFICE.value,
        "service_date": service_date,
        "submission_date": _submission_date(header["submission_date"], service_date, today),
        "pa_required": _bool(header["pa_required"], "pa_required") or pa_obtained,
        "pa_obtained": pa_obtained,
        "pa_number": pa_number,
        "billing": {
            "patient_birth_date": _date(header["patient_birth_date"], "patient_birth_date")
            if header["patient_birth_date"]
            else registration.birth_date,
            "patient_address": address,
            "policy": _table_policy(header, payer_id, registration, repo),
            "other_policies": other_policies,
            "institutional": institutional,
        },
    }


def _table_policy(header: dict, payer_id: str, registration, repo) -> dict | None:
    payer = repo.get_payer(payer_id)
    if payer is not None and payer.payer_type == PayerType.SELF_PAY:
        return None
    registered = registration.policies.get(payer_id)
    member_id = header["member_id"]
    if member_id and not (registered and registered.member_id == member_id):
        return {"member_id": member_id, "group_number": header["group_number"] or None}
    if registered is None:
        return None  # the claim check asks for the member ID
    policy = registered.model_dump(mode="json")
    if header["group_number"]:
        policy["group_number"] = header["group_number"]
    return policy


# ----- X12 837 ---------------------------------------------------------------------


def split_837(text: str) -> tuple[str, list[str]]:
    """The file's claims, each as a one-claim 837 (envelope + its provider, subscriber and
    patient loops + the claim) that read_837 can read. Also returns 837P or 837I."""
    text = text.lstrip("﻿ \r\n\t")
    if not text.startswith("ISA") or len(text) < 106:
        raise ImportFileError("This isn't an X12 837 file (it should start with an ISA segment)")
    element, component, terminator = text[3], text[104], text[105]
    text = text.replace("\r", "").replace("\n", "") if terminator not in "\r\n" else text
    segments = [s.strip() for s in text.split(terminator) if s.strip()]
    segments = [s.replace(element, "\x1f").replace(component, "\x1e") for s in segments]
    segments = [s.replace("*", "").replace(":", "").replace("\x1f", "*").replace("\x1e", ":") for s in segments]

    envelope: list[str] = []
    levels: dict[str, list[str]] = {}
    current: list[str] | None = None
    claims: list[list[str]] = []
    version = ""
    for segment in segments:
        tag, _, rest = segment.partition("*")
        parts = segment.split("*")
        if tag == "GS":
            version = parts[8] if len(parts) > 8 else ""
        if tag == "HL":
            code = parts[3] if len(parts) > 3 else ""
            levels[code] = [segment]
            if code == "20":
                levels.pop("22", None)
                levels.pop("23", None)
            elif code == "22":
                levels.pop("23", None)
            current = levels[code]
        elif tag == "CLM":
            context = [s for code in ("20", "22", "23") for s in levels.get(code, [])]
            current = [*context, segment]
            claims.append(current)
        elif tag in ("SE", "GE", "IEA"):
            current = None
        elif current is not None:
            current.append(segment)
        elif not levels:
            envelope.append(segment)
    if not claims:
        raise ImportFileError("No claims (CLM segments) were found in the 837 file")
    kind = "837I" if version.endswith("X223A2") else "837P"
    return kind, ["~".join([*envelope, *claim]) + "~" for claim in claims]


def parse_837(text: str, repo, registrations, today: date, payer_ids: dict[str, str]) -> tuple[str, list[ParsedClaim]]:
    kind, claim_texts = split_837(text)
    external = {external_id.upper(): payer_id for payer_id, external_id in payer_ids.items()}
    parsed = []
    for number, claim_text in enumerate(claim_texts, start=1):
        claim = ParsedClaim(ref="", where=f"claim {number} in the file")
        try:
            read = read_837(claim_text)
            claim.ref = read.claim_id
            body = _edi_claim(read, kind, repo, registrations, today, external, claim)
        except ValueError as err:
            claim.errors.append(str(err))
        else:
            _check(claim, body)
        parsed.append(claim)
    return kind, parsed


def _edi_claim(read: Claim837, kind: str, repo, registrations, today, external, claim: ParsedClaim) -> dict:
    institutional = kind == "837I"
    payer = _match_payer(read.policy.payer, repo, external)
    other_payers = [_match_payer(policy.payer, repo, external) for policy in read.other_policies]
    person = read.patient_party
    patient, registration = _match_patient(person, read.policy.holder.id, payer, repo, registrations, today)
    provider = next((p for p in repo.list_providers() if p.npi == read.provider.id), None)
    if provider is None:
        raise ValueError(f"No provider has NPI {read.provider.id or '(none given)'}")
    if not read.facility.name:
        facility_id = _default_facility(repo)
    else:
        facility = next(
            (f for f in repo.list_facilities() if f.facility_name.lower() == read.facility.name.lower()), None
        )
        if facility is None:
            raise ValueError(f"No facility is named {read.facility.name}")
        facility_id = facility.facility_id

    diagnoses = _edi_diagnoses(read.segments)
    if not diagnoses:
        raise ValueError("The claim has no diagnosis codes (HI segment)")
    lines = []
    for line in read.lines:
        pointer = diagnoses[0]
        if line.pointer:
            index = int(line.pointer.split(":")[0]) - 1
            if not 0 <= index < len(diagnoses):
                raise ValueError(f"Line {line.number} points at diagnosis {line.pointer}, which isn't on the claim")
            pointer = diagnoses[index]
        lines.append(
            {
                "cpt_code": line.procedure,
                "icd10_pointer": pointer,
                "units": int(float(line.units)) if line.units else 1,
                "modifier": line.modifiers[0] if line.modifiers else None,
                "charge_amount": float(line.charge) if line.charge else None,
                "revenue_code": line.revenue_code or None,
            }
        )
    if not lines:
        raise ValueError("The claim has no service lines")
    if institutional:
        # 837I lines don't point at diagnoses: link them in order so each diagnosis has one
        if len(diagnoses) > len(lines):
            raise ValueError(
                f"The claim lists {len(diagnoses)} diagnoses but only {len(lines)} service lines; "
                "each diagnosis needs a line here"
            )
        for line, diagnosis in zip(lines, diagnoses):
            line["icd10_pointer"] = diagnosis
        if len(diagnoses) > 1:
            claim.notes.append("837I lines don't say which diagnosis they treat: they were linked in order. Check them.")
        claim.notes.append("837I files don't give a place of service: it was set to 22 (outpatient hospital).")

    service_dates = [line.service_date for line in read.lines if line.service_date]
    if service_dates:
        service_date = min(service_dates)
    elif read.statement_period:
        service_date = read.statement_period.split(" – ")[0]
    else:
        raise ValueError("The claim has no service date (DTP 472 or 434)")
    service_date = _date(service_date, "service date")

    policies = [read.policy, *read.other_policies]
    payers = [payer, *other_payers]
    billing_policies = [
        None if p.payer_type == PayerType.SELF_PAY else _edi_policy(policy, registration.policies.get(p.payer_id))
        for policy, p in zip(policies, payers)
    ]
    return {
        "patient_id": patient.patient_id,
        "payer_id": payer.payer_id,
        "other_payer_ids": [p.payer_id for p in other_payers],
        "provider_id": provider.provider_id,
        "facility_id": facility_id,
        "diagnoses": diagnoses,
        "lines": lines,
        "claim_type": "Institutional" if institutional else "Professional",
        "place_of_service": PlaceOfService.OUTPATIENT_HOSPITAL.value if institutional else read.place_or_bill,
        "service_date": service_date,
        "submission_date": max(today, service_date),
        "pa_required": bool(read.prior_auth),
        "pa_obtained": bool(read.prior_auth),
        "pa_number": read.prior_auth or None,
        "billing": {
            "patient_birth_date": _date(person.birth_date, "patient date of birth")
            if person.birth_date
            else registration.birth_date,
            "patient_address": _edi_address(person) or registration.address.model_dump(mode="json"),
            "policy": billing_policies[0],
            "other_policies": [p for p in billing_policies[1:] if p is not None],
            "institutional": {
                "type_of_bill": read.place_or_bill + read.frequency,
                "admission_type": read.admission_type,
                "admission_source": read.admission_source,
                "patient_status": read.patient_status,
            }
            if institutional
            else None,
        },
    }


def _default_facility(repo) -> str:
    """The facility when the file doesn't say: FAC001 (the main campus), or the
    organisation's only facility."""
    facilities = [f.facility_id for f in repo.list_facilities()]
    if "FAC001" in facilities:
        return "FAC001"
    if len(facilities) == 1:
        return facilities[0]
    raise ValueError(f"Give the facility (facility_id): this organisation has {len(facilities)}")


def _match_payer(party: Party, repo, external: dict[str, str]):
    payers = repo.list_payers()
    payer_id = external.get(party.id.upper(), party.id.upper())
    payer = next((p for p in payers if p.payer_id == payer_id), None)
    payer = payer or next((p for p in payers if p.payer_name.lower() == party.name.lower()), None)
    if payer is None:
        raise ValueError(f"No payer matches {party.name or '(no name)'} ({party.id or 'no ID'})")
    return payer


def _match_patient(person: Party, member_id: str, payer, repo, registrations, today):
    """The one registered patient with this name whose date of birth (or member ID with
    this payer) matches."""
    if not person.name:
        raise ValueError("The claim doesn't name the patient")
    name = f"{person.first_name} {person.name}".strip()
    page = repo.list_patients(PatientQuery(search=name, page_size=50))
    candidates = [
        p
        for p in page.items
        if p.last_name.lower() == person.name.lower() and p.first_name.lower() == person.first_name.lower()
    ]
    matches = []
    for patient in candidates:
        registration = registrations.get(patient, repo.get_payer(patient.primary_payer_id), today)
        policy = registration.policies.get(payer.payer_id)
        if person.birth_date and registration.birth_date.isoformat() == person.birth_date:
            matches.append((patient, registration))
        elif not person.birth_date and policy is not None and policy.member_id == member_id:
            matches.append((patient, registration))
    if len(matches) == 1:
        return matches[0]
    if not candidates:
        raise ValueError(f"No registered patient is named {name}")
    if not matches:
        raise ValueError(f"No registered patient named {name} has that date of birth")
    raise ValueError(f"More than one registered patient matches {name}: enter this claim on the form")


def _edi_diagnoses(segments: list[str]) -> list[str]:
    codes = []
    for segment in segments:
        parts = segment.split("*")
        if parts[0] != "HI":
            continue
        for item in parts[1:]:
            qualifier, _, code = item.partition(":")
            if qualifier in _DIAGNOSIS_QUALIFIERS and code:
                codes.append(f"{code[:3]}.{code[3:]}" if len(code) > 3 else code)
    return list(dict.fromkeys(codes))


def _edi_policy(policy: Policy, registered) -> dict:
    relationship = _RELATIONSHIPS.get(policy.relationship, Relationship.OTHER)
    if registered is not None and registered.member_id == policy.holder.id:
        return registered.model_dump(mode="json")
    holder = {"member_id": policy.holder.id, "group_number": policy.group_number or None, "relationship": relationship}
    if relationship != Relationship.SELF:
        holder.update(
            first_name=policy.holder.first_name or None,
            last_name=policy.holder.name or None,
            birth_date=policy.holder.birth_date or None,
            sex=policy.holder.sex or None,
        )
    return holder


def _edi_address(person: Party) -> dict | None:
    if not person.address:
        return None
    return {
        "line1": person.address[0],
        "line2": person.address[1] if len(person.address) > 1 else None,
        "city": person.city,
        "state": person.state,
        "zip_code": person.zip_code,
    }


# ----- shared ----------------------------------------------------------------------


def _check(claim: ParsedClaim, body: dict) -> None:
    """The same field checks as a claim typed into the form."""
    try:
        claim.body = ClaimCreate.model_validate(body)
    except ValidationError as err:
        claim.errors += [_message(e) for e in err.errors()]


def _message(error: dict) -> str:
    message = error["msg"].removeprefix("Value error, ")
    where = ".".join(str(part) for part in error["loc"])
    return f"{where}: {message}" if where else message


def _split(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[|;,]", value) if part.strip()]


def _date(value: str, column: str) -> date:
    value = value.strip()[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", value.strip()) else value.strip()
    for layout in ("%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(value, layout).date()
        except ValueError:
            continue
    raise ValueError(f"{column} isn't a date: {value!r} (use YYYY-MM-DD)")


def _submission_date(value: str, service_date: date, today: date) -> date:
    return _date(value, "submission_date") if value else max(today, service_date)


def _number(value: str, column: str, kind):
    try:
        number = float(value.replace("$", "").replace(",", ""))
    except ValueError:
        raise ValueError(f"{column} isn't a number: {value!r}") from None
    return int(number) if kind is int else number


def _bool(value: str, column: str) -> bool:
    text = value.strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    raise ValueError(f"{column} should be yes or no, not {value!r}")
