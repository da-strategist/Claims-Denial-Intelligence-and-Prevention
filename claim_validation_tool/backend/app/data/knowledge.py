"""The clarification assistant's knowledge base: one citable source per reference-table row.

Each source carries readable text (what the LLM reads and the specialist sees) and lookup
keys such as "cpt:93458", "icd10:I25.10", "payer:PAY002", or "carc:197", so a claim's
codes find the sources that govern them exactly. No outside documents are used.
"""

from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.data.repository import _read_table, get_repository
from app.models import SourceType

# What each CARC group code means for who owes the balance
CARC_GROUPS = {
    "CO": "Contractual Obligation: the provider absorbs the amount and can't bill the patient",
    "PR": "Patient Responsibility: the patient may be billed",
    "OA": "Other Adjustment",
    "PI": "Payer Initiated Reduction",
}


@dataclass(frozen=True)
class Source:
    source_type: SourceType
    reference_id: str
    title: str
    text: str
    keys: frozenset[str]
    data: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    @property
    def id(self) -> str:
        return f"{self.source_type}:{self.reference_id}"


def _codes(value: str) -> list[str]:
    return [code.strip() for code in str(value).split("|") if code.strip()]


def _carc_sources(data_dir: Path) -> list[Source]:
    sources = []
    for row in _read_table(data_dir, "ref_carc_codes").to_dict("records"):
        code, group = row["carc_code"], row["group_code"]
        meaning = CARC_GROUPS.get(group, group)
        sources.append(
            Source(
                SourceType.CARC,
                code,
                f"CARC {code}: {row['description']}",
                f"Claim Adjustment Reason Code {code}: {row['description']}. "
                f"Group {group} ({meaning}).",
                frozenset({f"carc:{code}"}),
                row,
            )
        )
    return sources


def _rarc_sources(data_dir: Path) -> list[Source]:
    return [
        Source(
            SourceType.RARC,
            row["rarc_code"],
            f"RARC {row['rarc_code']}: {row['description']}",
            f"Remittance Advice Remark Code {row['rarc_code']}: {row['description']}.",
            frozenset({f"rarc:{row['rarc_code']}"}),
            row,
        )
        for row in _read_table(data_dir, "ref_rarc_codes").to_dict("records")
    ]


def _ncci_sources(data_dir: Path) -> list[Source]:
    sources = []
    for row in _read_table(data_dir, "ref_ncci_ptp_edits").to_dict("records"):
        col1, col2 = row["column_1_cpt"], row["column_2_cpt"]
        ended = f", terminated {row['termination_date']}" if row["termination_date"] else ""
        sources.append(
            Source(
                SourceType.NCCI_EDIT,
                row["edit_id"],
                f"NCCI PTP edit {col1} / {col2}",
                f"NCCI procedure-to-procedure edit {row['edit_id']}: column 1 CPT {col1} with "
                f"column 2 CPT {col2}. Modifier indicator {row['modifier_indicator']} "
                f"({row['modifier_indicator_desc']}). Rationale: {row['rationale']}. "
                f"When both are billed for the same patient and date, CPT {col2} is denied "
                + (
                    "unless a modifier (59 or XE/XS/XP/XU) documents a distinct service."
                    if row["modifier_indicator"] == "1"
                    else "and no modifier bypasses the edit."
                )
                + f" Effective {row['effective_date']}{ended}. Source: {row['source']}.",
                frozenset({f"cpt:{col1}", f"cpt:{col2}"}),
                row,
            )
        )
    return sources


def _mue_sources(data_dir: Path) -> list[Source]:
    return [
        Source(
            SourceType.MUE,
            row["mue_id"],
            f"MUE for CPT {row['cpt_code']}: {row['max_units_per_day']} per day",
            f"Medically Unlikely Edit {row['mue_id']}: CPT {row['cpt_code']} allows at most "
            f"{row['max_units_per_day']} unit(s) per day ({row['adjudication_type']} "
            f"adjudication). Rationale: {row['mue_rationale']}. Units above the limit are "
            f"denied. Effective {row['effective_date']}. Source: {row['source']}.",
            frozenset({f"cpt:{row['cpt_code']}"}),
            row,
        )
        for row in _read_table(data_dir, "ref_mue_limits").to_dict("records")
    ]


def _coverage_sources(data_dir: Path) -> list[Source]:
    sources = []
    for row in _read_table(data_dir, "ref_lcd_ncd_policies").to_dict("records"):
        cpts, icd10s = _codes(row["cpt_codes"]), _codes(row["covered_icd10"])
        sources.append(
            Source(
                SourceType.COVERAGE_POLICY,
                row["policy_id"],
                f"{row['policy_id']}: {row['title']}",
                f"{row['policy_type']} {row['policy_id']} ({row['title']}, {row['mac_region']}) "
                f"covers CPT {', '.join(cpts)}. Covered ICD-10 codes: {', '.join(icd10s)}. "
                f"Covered when: {row['covered_conditions']}. Not covered: "
                f"{row['non_covered_conditions']}. Documentation required: "
                f"{row['documentation_required']}.",
                frozenset({*(f"cpt:{c}" for c in cpts), *(f"icd10:{c}" for c in icd10s)}),
                {**row, "cpt_list": cpts, "icd10_list": icd10s},
            )
        )
    return sources


def _payer_sources(data_dir: Path) -> tuple[list[Source], dict[str, str]]:
    sources, names = [], {}
    for row in _read_table(data_dir, "dim_payers").to_dict("records"):
        payer_id, name = row["payer_id"], row["payer_name"]
        names[payer_id] = name
        sources.append(
            Source(
                SourceType.PAYER,
                payer_id,
                f"Payer profile: {name}",
                f"{name} ({row['payer_type']}, {payer_id}, policy prefix "
                f"{row['policy_prefix']}): historical denial rate "
                f"{float(row['denial_rate']):.0%}, pays in {row['avg_days_to_pay']} days on "
                f"average, prior authorization strictness score {float(row['pa_strictness']):.2f} "
                f"(0-1 scale). Status: {row['status']}. This profile does not list which "
                "services require prior authorization.",
                frozenset({f"payer:{payer_id}"}),
                row,
            )
        )
    return sources, names


def _contract_sources(data_dir: Path, payer_names: dict[str, str], cipher=None) -> list[Source]:
    sources = []
    for row in _read_table(data_dir, "dim_payer_contracts", cipher).to_dict("records"):
        payer_id, category = row["payer_id"], row["cpt_category"]
        name = payer_names.get(payer_id, payer_id)
        end = row["end_date"] or "open-ended"
        sources.append(
            Source(
                SourceType.PAYER_CONTRACT,
                row["contract_id"],
                f"{name} contract: {category}",
                f"Payer contract {row['contract_id']}: {name} ({payer_id}) reimburses "
                f"{float(row['reimbursement_pct_of_charge']):.1%} of billed charges for "
                f"{category} services, effective {row['effective_date']} to {end}. "
                f"Status: {row['status']}.",
                frozenset({f"payer:{payer_id}", f"contract:{payer_id}:{category}"}),
                row,
            )
        )
    return sources


def _fee_schedule_sources(data_dir: Path) -> list[Source]:
    return [
        Source(
            SourceType.FEE_SCHEDULE,
            row["cpt_code"],
            f"Medicare fee schedule: CPT {row['cpt_code']}",
            f"Medicare Physician Fee Schedule for CPT {row['cpt_code']} ({row['description']}, "
            f"{row['category']}), {row['locality']}, MAC {row['mac']}: 2025 payment "
            f"${float(row['medicare_payment_facility_2025']):,.2f} in a facility, "
            f"${float(row['medicare_payment_nonfacility_2025']):,.2f} non-facility "
            f"(total RVUs {row['total_rvu_facility']} / {row['total_rvu_nonfacility']}, "
            f"conversion factor {row['conversion_factor_2025']}). 2024 payment "
            f"${float(row['medicare_payment_facility_2024']):,.2f} / "
            f"${float(row['medicare_payment_nonfacility_2024']):,.2f}.",
            frozenset({f"cpt:{row['cpt_code']}"}),
            row,
        )
        for row in _read_table(data_dir, "ref_physician_fee_schedule").to_dict("records")
    ]


@dataclass(frozen=True)
class KnowledgeBase:
    sources: tuple[Source, ...]
    payer_names: dict[str, str]

    @classmethod
    def load(cls, data_dir: Path, cipher=None) -> "KnowledgeBase":
        """`cipher` decrypts the organisation's own tables (its payer contracts)."""
        payers, payer_names = _payer_sources(data_dir)
        sources = [
            *_coverage_sources(data_dir),
            *_ncci_sources(data_dir),
            *_mue_sources(data_dir),
            *payers,
            *_contract_sources(data_dir, payer_names, cipher),
            *_carc_sources(data_dir),
            *_rarc_sources(data_dir),
            *_fee_schedule_sources(data_dir),
        ]
        return cls(tuple(sources), payer_names)

    def counts(self) -> dict[SourceType, int]:
        return dict(Counter(source.source_type for source in self.sources))


@lru_cache(maxsize=None)
def get_knowledge_base(org_id: str) -> KnowledgeBase:
    """The organisation's knowledge base, from the same data directory as its claims."""
    repo = get_repository(org_id)
    return KnowledgeBase.load(repo.data_dir, repo.cipher)
