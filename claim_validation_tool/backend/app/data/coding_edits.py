"""Coding checks on a claim's service lines, from the organisation's reference tables:
NCCI procedure-to-procedure edits, MUE unit limits, LCD/NCD coverage policies, and whether
each line's diagnosis fits its procedure at all.

The repository turns the results into claim fields that rules test (ncci_conflict,
mue_exceeded, diagnosis_not_covered, diagnosis_procedure_mismatch); AI Fix uses the details
to say which lines and which reference record. One claim is one patient and date, and units
of a code are added up across lines, as the assistant reads the same tables (knowledge.py).

Diagnoses are judged per line, by the diagnosis the line points to, as payers adjudicate
them. A policy's procedure needs that diagnosis on the policy's covered list. A procedure
without a policy, in a specialty category, needs a diagnosis from a related ICD-10 chapter
(PLAUSIBLE_CHAPTERS): a rough screen, not a crosswalk, so its rule is a warning.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

# Modifiers that report a distinct service, bypassing an NCCI edit whose indicator is 1
NCCI_BYPASS_MODIFIERS = frozenset({"59", "XE", "XS", "XP", "XU"})

# ICD-10-CM chapters by code range (first letter and two digits), for the plausibility screen
_CHAPTERS: tuple[tuple[str, str, str], ...] = (
    ("A00", "B99", "Infectious"),
    ("C00", "D49", "Neoplasm"),
    ("D50", "D89", "Blood"),
    ("E00", "E89", "Endocrine"),
    ("F01", "F99", "Mental"),
    ("G00", "G99", "Nervous"),
    ("H00", "H59", "Eye"),
    ("H60", "H95", "Ear"),
    ("I00", "I99", "Circulatory"),
    ("J00", "J99", "Respiratory"),
    ("K00", "K95", "Digestive"),
    ("L00", "L99", "Skin"),
    ("M00", "M99", "Musculoskeletal"),
    ("N00", "N99", "Genitourinary"),
    ("O00", "O9A", "Pregnancy"),
    ("P00", "P96", "Perinatal"),
    ("Q00", "Q99", "Congenital"),
    ("R00", "R99", "Symptoms"),
    ("S00", "T88", "Injury"),
    ("V00", "Y99", "External causes"),
    ("Z00", "Z99", "Health factors"),
)

# Symptoms and encounter reasons (screening, aftercare, pre-op) support most services
ALWAYS_PLAUSIBLE = frozenset({"Symptoms", "Health factors"})

# Procedure category -> the chapters its diagnoses come from. Categories not listed (office
# visits, labs, imaging, preventive care) go with any diagnosis and aren't screened. A
# category name the organisation uses differently is simply not screened
PLAUSIBLE_CHAPTERS: dict[str, frozenset[str]] = {
    "Cardiology": frozenset({"Circulatory"}),
    "Behavioral": frozenset({"Mental"}),
    "Neurology": frozenset({"Nervous", "Circulatory", "Musculoskeletal", "Injury"}),
    "OB/GYN": frozenset({"Pregnancy", "Genitourinary", "Neoplasm"}),
    "Oncology": frozenset({"Neoplasm", "Blood"}),
    "Orthopedics": frozenset({"Musculoskeletal", "Injury"}),
    "Pulmonology": frozenset({"Respiratory", "Neoplasm", "Nervous"}),
    "Rehab": frozenset({"Musculoskeletal", "Injury", "Nervous", "Circulatory"}),
    "Surgery": frozenset({"Digestive", "Neoplasm", "Skin", "Injury", "Genitourinary"}),
}


def icd10_chapter(code: str) -> str | None:
    """The ICD-10-CM chapter a code belongs to, from its first three characters."""
    key = code.strip().upper()[:3]
    if len(key) < 3 or not key[0].isalpha():
        return None
    for start, end, chapter in _CHAPTERS:
        if start <= key <= end:
            return chapter
    return None


@dataclass(frozen=True)
class NcciConflict:
    edit_id: str
    column_1_cpt: str
    column_2_cpt: str
    modifier_allowed: bool  # indicator 1: a distinct-service modifier can bypass the edit
    rationale: str
    line_number: int  # the column 2 line, the one the payer denies


@dataclass(frozen=True)
class MueExcess:
    mue_id: str
    cpt_code: str
    units: int
    limit: int
    rationale: str


@dataclass(frozen=True)
class UncoveredService:
    policy_id: str
    title: str
    cpt_code: str
    covered_icd10: tuple[str, ...]
    documentation_required: str
    line_number: int
    diagnosis: str  # the diagnosis the line points to


@dataclass(frozen=True)
class DiagnosisMismatch:
    line_number: int
    cpt_code: str
    category: str  # the procedure's
    diagnosis: str
    chapter: str  # the diagnosis's
    expected: tuple[str, ...]  # chapters that would fit the procedure


@dataclass(frozen=True)
class CodingResult:
    ncci: tuple[NcciConflict, ...] = ()
    mue: tuple[MueExcess, ...] = ()
    uncovered: tuple[UncoveredService, ...] = ()
    mismatched: tuple[DiagnosisMismatch, ...] = ()

    def flags(self) -> dict[str, bool]:
        """The claim fields rules test."""
        return {
            "ncci_conflict": bool(self.ncci),
            "mue_exceeded": bool(self.mue),
            "diagnosis_not_covered": bool(self.uncovered),
            "diagnosis_procedure_mismatch": bool(self.mismatched),
        }


NO_FLAGS = CodingResult().flags()


def _codes(value: str) -> tuple[str, ...]:
    return tuple(code.strip() for code in str(value).split("|") if code.strip())


def _table(data_dir: Path, name: str) -> pd.DataFrame:
    # Imported here: the repository imports this module
    from app.data.repository import _read_table

    try:
        return _read_table(data_dir, name)
    except FileNotFoundError:
        return pd.DataFrame()


@dataclass(frozen=True)
class CodingEdits:
    ncci: tuple[dict[str, Any], ...]
    mue: dict[str, dict[str, Any]]  # cpt_code -> MUE row
    policies: tuple[dict[str, Any], ...]  # with cpt_list and icd10_list
    categories: dict[str, str]  # cpt_code -> category (dim_cpt_codes)

    @classmethod
    def load(cls, data_dir: Path) -> "CodingEdits":
        """The organisation's tables; one that's missing checks nothing."""
        ncci = _table(data_dir, "ref_ncci_ptp_edits")
        mue = _table(data_dir, "ref_mue_limits")
        policies = _table(data_dir, "ref_lcd_ncd_policies")
        procedures = _table(data_dir, "dim_cpt_codes")
        return cls(
            ncci=tuple(ncci.to_dict("records")),
            mue={row["cpt_code"]: row for row in mue.to_dict("records")},
            policies=tuple(
                {**row, "cpt_list": _codes(row["cpt_codes"]), "icd10_list": _codes(row["covered_icd10"])}
                for row in policies.to_dict("records")
            ),
            categories={row["cpt_code"]: row["category"] for row in procedures.to_dict("records")},
        )

    def check(
        self, lines: Iterable[Mapping[str, Any]], diagnoses: Iterable[str], service_date: str
    ) -> CodingResult:
        """Check one claim's lines (cpt_code, modifier, units, icd10_pointer, and line_number
        if known) against the edits in effect on its service date (YYYY-MM-DD). `diagnoses`
        starts with the primary. A line pointing at a code no longer on the claim (its primary
        was corrected by AI Fix) is read as pointing at the primary."""
        diagnoses = [code.strip().upper() for code in diagnoses if code and code.strip()]
        primary = diagnoses[0] if diagnoses else ""
        lines = [
            {
                "cpt_code": str(line["cpt_code"]),
                "modifier": str(line.get("modifier") or "").upper(),
                "units": int(line.get("units") or 1),
                "line_number": int(line.get("line_number") or number),
                "diagnosis": _pointed(line.get("icd10_pointer"), diagnoses, primary),
            }
            for number, line in enumerate(lines, start=1)
        ]
        by_cpt: dict[str, list[dict]] = {}
        for line in lines:
            by_cpt.setdefault(line["cpt_code"], []).append(line)

        ncci = []
        for edit in self.ncci:
            first, second = by_cpt.get(edit["column_1_cpt"]), by_cpt.get(edit["column_2_cpt"])
            if not first or not second or not _in_effect(edit, service_date):
                continue
            allowed = edit["modifier_indicator"] == "1"
            for line in second:
                bypassed = allowed and (
                    line["modifier"] in NCCI_BYPASS_MODIFIERS
                    or any(other["modifier"] in NCCI_BYPASS_MODIFIERS for other in first)
                )
                if not bypassed:
                    ncci.append(
                        NcciConflict(
                            edit_id=edit["edit_id"],
                            column_1_cpt=edit["column_1_cpt"],
                            column_2_cpt=edit["column_2_cpt"],
                            modifier_allowed=allowed,
                            rationale=edit["rationale"],
                            line_number=line["line_number"],
                        )
                    )

        mue = []
        for cpt, cpt_lines in by_cpt.items():
            limit = self.mue.get(cpt)
            units = sum(line["units"] for line in cpt_lines)
            if limit is not None and units > int(limit["max_units_per_day"]):
                mue.append(
                    MueExcess(
                        mue_id=limit["mue_id"],
                        cpt_code=cpt,
                        units=units,
                        limit=int(limit["max_units_per_day"]),
                        rationale=limit["mue_rationale"],
                    )
                )

        uncovered, mismatched = [], []
        policies_by_cpt: dict[str, list[dict]] = {}
        for policy in self.policies:
            for cpt in policy["cpt_list"]:
                policies_by_cpt.setdefault(cpt, []).append(policy)
        for line in lines:
            cpt, diagnosis = line["cpt_code"], line["diagnosis"]
            if not diagnosis:
                continue
            if cpt in policies_by_cpt:
                uncovered.extend(
                    UncoveredService(
                        policy_id=policy["policy_id"],
                        title=policy["title"],
                        cpt_code=cpt,
                        covered_icd10=policy["icd10_list"],
                        documentation_required=policy["documentation_required"],
                        line_number=line["line_number"],
                        diagnosis=diagnosis,
                    )
                    for policy in policies_by_cpt[cpt]
                    if diagnosis not in policy["icd10_list"]
                )
                continue  # the policy is the better judge; don't screen it twice
            category = self.categories.get(cpt, "")
            expected = PLAUSIBLE_CHAPTERS.get(category)
            chapter = icd10_chapter(diagnosis)
            if expected and chapter and chapter not in expected | ALWAYS_PLAUSIBLE:
                mismatched.append(
                    DiagnosisMismatch(
                        line_number=line["line_number"],
                        cpt_code=cpt,
                        category=category,
                        diagnosis=diagnosis,
                        chapter=chapter,
                        expected=tuple(sorted(expected)),
                    )
                )
        return CodingResult(tuple(ncci), tuple(mue), tuple(uncovered), tuple(mismatched))


def _pointed(pointer: Any, diagnoses: list[str], primary: str) -> str:
    code = str(pointer or "").strip().upper()
    return code if code in diagnoses else primary


def _in_effect(edit: Mapping[str, Any], service_date: str) -> bool:
    starts, ends = edit.get("effective_date") or "", edit.get("termination_date") or ""
    return (not starts or starts <= service_date) and (not ends or service_date < ends)
