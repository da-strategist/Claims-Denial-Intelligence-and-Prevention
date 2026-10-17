"""The organisation's identifiers for 837 claim files, from RCM_EDI_SETTINGS_FILE.

These identify who sends the file (the submitter), who receives it (the clearinghouse),
the billing provider, and each payer's electronic payer ID. They aren't in the claim
data, so they live in a settings file (git-ignored). Until every one is filled in, and
`mode` is "production", files are marked as test files (ISA15 = T) and say what's missing.

    {
      "mode": "test",
      "submitter": {"id": "", "name": "", "contact_name": "", "phone": ""},
      "receiver": {"id": "", "name": ""},
      "billing_provider": {"name": "", "npi": "", "tax_id": "",
                           "address": {"line1": "", "city": "", "state": "", "zip_code": ""}},
      "payer_ids": {"PAY001": "", "PAY002": ""}
    }
"""

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

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

    def missing(self, payer_ids: list[str]) -> list[str]:
        """Settings a live file for these payers still needs, in plain words."""
        gaps = []
        checks = [
            (self.submitter.id, "submitter ID"),
            (self.submitter.name, "submitter name"),
            (self.submitter.contact_name, "submitter contact"),
            (self.submitter.phone, "submitter phone"),
            (self.receiver.id, "clearinghouse (receiver) ID"),
            (self.receiver.name, "clearinghouse name"),
            (self.billing_provider.name, "billing provider name"),
            (_npi_ok(self.billing_provider.npi), "billing provider NPI"),
            (_digits(self.billing_provider.tax_id, 9), "billing provider tax ID (9-digit EIN)"),
            (self.billing_provider.address.line1, "billing provider address"),
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


def load_edi_settings() -> EdiSettings:
    """Read on each use, so edits to the file apply without a restart."""
    path = Path(os.environ.get("RCM_EDI_SETTINGS_FILE", DEFAULT_EDI_SETTINGS_FILE))
    if not path.exists():
        return EdiSettings()
    return EdiSettings.model_validate(json.loads(path.read_text()))
