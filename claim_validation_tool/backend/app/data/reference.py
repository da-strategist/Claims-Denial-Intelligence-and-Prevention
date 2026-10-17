"""Reference tables the AI Fix suggester cites: CARC/RARC codes, payer contracts, ICD-10 and CPT codes."""

from dataclasses import dataclass
from functools import lru_cache

from app.data.repository import ClaimsRepository, _read_table, get_repository


@dataclass(frozen=True)
class ReferenceData:
    carc: dict[str, dict]  # carc_code -> {description, group_code}
    rarc: dict[str, dict]  # rarc_code -> {description}
    contracts: dict[tuple[str, str], dict]  # (payer_id, cpt_category) -> contract row
    icd10: dict[str, dict]  # icd10_code -> {description, body_system, ...}
    cpt: dict[str, dict]  # cpt_code -> {description, category, ...}

    @classmethod
    def load(cls, repo: ClaimsRepository) -> "ReferenceData":
        def by_key(name: str, key: str) -> dict[str, dict]:
            df = _read_table(repo.data_dir, name)
            return {row[key]: row for row in df.to_dict("records")}

        contracts = _read_table(repo.data_dir, "dim_payer_contracts", repo.cipher)
        contracts = contracts[contracts["status"] == "Active"]
        return cls(
            carc=by_key("ref_carc_codes", "carc_code"),
            rarc=by_key("ref_rarc_codes", "rarc_code"),
            contracts={
                (row["payer_id"], row["cpt_category"]): row for row in contracts.to_dict("records")
            },
            icd10=by_key("dim_icd10_codes", "icd10_code"),
            cpt=by_key("dim_cpt_codes", "cpt_code"),
        )

    def icd10_siblings(self, code: str) -> list[str]:
        """Other known codes in the same ICD-10 category (e.g. E11.65 for E11.9)."""
        category = code.split(".")[0]
        return sorted(c for c in self.icd10 if c.split(".")[0] == category and c != code)


def contract_rate(reference: ReferenceData, payer_id: str, cpt_category: str) -> float | None:
    contract = reference.contracts.get((payer_id, cpt_category))
    return float(contract["reimbursement_pct_of_charge"]) if contract else None


@lru_cache(maxsize=None)
def get_reference_data(org_id: str) -> ReferenceData:
    """The organisation's reference tables, from the same data directory as its claims."""
    return ReferenceData.load(get_repository(org_id))
