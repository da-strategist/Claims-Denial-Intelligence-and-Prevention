"""An organisation's identifiers for 837 claim files, from edi_settings.json in its folder.

These identify who sends the file (the submitter), who receives it (the clearinghouse),
the billing provider, each payer's electronic payer ID, and a ZIP+4 for any facility whose
address on file has only 5 digits. They aren't in the claim data, so they live in a settings
file (git-ignored), which administrators edit on the Users page. Until every one a file needs
is filled in, and `mode` is "production", files are marked as test files (ISA15 = T) and say
what's missing. A file going back to the hospital's own billing system names no clearinghouse,
so a hospital that only validates here never needs one.

    {
      "mode": "test",
      "submitter": {"id": "", "name": "", "contact_name": "", "phone": ""},
      "receiver": {"id": "", "name": ""},
      "billing_provider": {"name": "", "npi": "", "tax_id": "",
                           "address": {"line1": "", "city": "", "state": "", "zip_code": ""}},
      "payer_ids": {"PAY001": "", "PAY002": ""},
      "facility_zip_codes": {"FAC001": ""}
    }
"""

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.data.orgs import org_file
from app.data.secure_files import write_text

DEFAULT_EDI_SETTINGS_FILE = Path(__file__).resolve().parents[2] / "edi_settings.json"


class Party(BaseModel):
    id: str = ""
    name: str = ""


class Submitter(Party):
    contact_name: str = ""
    phone: str = ""


class SettingsAddress(BaseModel):
    line1: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""


class BillingProvider(BaseModel):
    name: str = ""
    npi: str = ""
    tax_id: str = ""
    address: SettingsAddress = Field(default_factory=SettingsAddress)


class EdiSettings(BaseModel):
    mode: Literal["test", "production"] = "test"
    submitter: Submitter = Field(default_factory=Submitter)
    receiver: Party = Field(default_factory=Party)
    billing_provider: BillingProvider = Field(default_factory=BillingProvider)
    payer_ids: dict[str, str] = Field(default_factory=dict)
    facility_zip_codes: dict[str, str] = Field(
        default_factory=dict, description="ZIP+4 by facility, for addresses on file with 5 digits"
    )

    def missing(self, payer_ids: list[str], needs_clearinghouse: bool = True) -> list[str]:
        """Settings a live file for these payers still needs, in plain words."""
        gaps = []
        checks = [
            (self.submitter.id, "submitter ID"),
            (self.submitter.name, "submitter name"),
            (self.submitter.contact_name, "submitter contact"),
            (self.submitter.phone, "submitter phone"),
            *(
                [
                    (self.receiver.id, "clearinghouse (receiver) ID"),
                    (self.receiver.name, "clearinghouse name"),
                ]
                if needs_clearinghouse
                else []
            ),
            (self.billing_provider.name, "billing provider name"),
            (_npi_ok(self.billing_provider.npi), "billing provider NPI"),
            (_digits(self.billing_provider.tax_id, 9), "billing provider tax ID (9-digit EIN)"),
            (self.billing_provider.address.line1, "billing provider address"),
            (self.billing_provider.address.city, "billing provider city"),
            (self.billing_provider.address.state, "billing provider state"),
            (_digits(self.billing_provider.address.zip_code, 9), "billing provider ZIP+4 (9 digits)"),
        ]
        gaps = [label for value, label in checks if not value]
        gaps += [f"electronic payer ID for {p}" for p in payer_ids if not self.payer_ids.get(p)]
        return gaps


def _digits(value: str, length: int) -> bool:
    return value.isdigit() and len(value) == length


def _npi_ok(npi: str) -> bool:
    """10 digits passing the NPI check digit (Luhn with the 80840 prefix)."""
    if not _digits(npi, 10):
        return False
    total = 0
    for index, char in enumerate(reversed("80840" + npi[:9])):
        digit = int(char)
        if index % 2 == 0:
            digit *= 2
            digit = digit - 9 if digit > 9 else digit
        total += digit
    return (10 - total % 10) % 10 == int(npi[9])


def cleaned(settings: EdiSettings) -> tuple[EdiSettings, list[str]]:
    """Settings as entered on the screen, tidied, and what's wrong with them. Blanks are fine,
    so they can be filled in over time; what's filled in has to be usable. A file's identifiers
    must fit, because the 837 would otherwise cut them short or break on a separator."""
    data = settings.model_dump()
    for section in ("submitter", "receiver", "billing_provider"):
        data[section] = {k: v.strip() if isinstance(v, str) else v for k, v in data[section].items()}
    provider, address, submitter = data["billing_provider"], data["billing_provider"]["address"], data["submitter"]
    address.update({k: v.strip() for k, v in address.items()})
    provider["npi"] = _only_digits(provider["npi"])
    provider["tax_id"] = _only_digits(provider["tax_id"])
    address["zip_code"] = _only_digits(address["zip_code"])
    address["state"] = address["state"].upper()
    submitter["phone"] = _only_digits(submitter["phone"])
    data["payer_ids"] = {k: v.strip() for k, v in data["payer_ids"].items() if v.strip()}
    data["facility_zip_codes"] = {
        k: _only_digits(v) for k, v in data["facility_zip_codes"].items() if v.strip()
    }

    problems = []
    for label, value in (("Submitter ID", submitter["id"]), ("Clearinghouse ID", data["receiver"]["id"])):
        if value and not re.fullmatch(r"[A-Za-z0-9 ._-]{1,15}", value):
            problems.append(f"{label} can be up to 15 letters and numbers")
    for label, value in (
        ("Submitter name", submitter["name"]),
        ("Submitter contact", submitter["contact_name"]),
        ("Clearinghouse name", data["receiver"]["name"]),
        ("Billing provider name", provider["name"]),
        ("Billing provider address", address["line1"]),
        ("Billing provider city", address["city"]),
    ):
        if len(value) > 55:
            problems.append(f"{label} can be up to 55 characters")
    if submitter["phone"] and not _digits(submitter["phone"], 10):
        problems.append("Submitter phone needs 10 digits")
    if provider["npi"] and not _npi_ok(provider["npi"]):
        problems.append("Billing provider NPI isn't a valid NPI: it needs 10 digits and a correct check digit")
    if provider["tax_id"] and not _digits(provider["tax_id"], 9):
        problems.append("Billing provider tax ID needs 9 digits")
    if address["state"] and not re.fullmatch(r"[A-Z]{2}", address["state"]):
        problems.append("Billing provider state needs 2 letters")
    if address["zip_code"] and not _digits(address["zip_code"], 9):
        problems.append("Billing provider ZIP+4 needs 9 digits")
    for payer_id, value in data["payer_ids"].items():
        if not re.fullmatch(r"[A-Za-z0-9-]{1,80}", value):
            problems.append(f"Electronic payer ID for {payer_id} can only have letters, numbers, and hyphens")
    for facility_id, value in data["facility_zip_codes"].items():
        if not _digits(value, 9):
            problems.append(f"ZIP+4 for {facility_id} needs 9 digits")
    return EdiSettings.model_validate(data), problems


def _only_digits(value: str) -> str:
    """Digits typed with their usual punctuation: 56-1234567, (704) 555-0100, 28211-1234. Anything
    else stays, so it's reported rather than quietly dropped."""
    return re.sub(r"[\s().-]", "", value)


def save_edi_settings(org_id: str, settings: EdiSettings) -> None:
    write_text(org_file(org_id, "edi_settings.json"), json.dumps(settings.model_dump(), indent=2), None)


def load_edi_settings(org_id: str) -> EdiSettings:
    """The organisation's settings, read on each use so edits apply without a restart."""
    path = org_file(org_id, "edi_settings.json")
    if not path.exists():
        return EdiSettings()
    return EdiSettings.model_validate(json.loads(path.read_text()))
