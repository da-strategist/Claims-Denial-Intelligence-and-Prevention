"""An organisation built from CMS's synthetic Medicare inpatient claims (data.cms.gov,
"Synthetic Medicare Enrollment, Fee-for-Service Claims, and Prescription Drug Event").

The download's inpatient.csv and beneficiary file are in CMS's research layout (pipe-
separated, one row per revenue-center line). One state's claims become one organisation,
in the same tables as every other organisation:

- each beneficiary becomes a registered patient (PAT8xxxxx). CMS gives no names, so they
  are "Beneficiary <id>"; birth date, sex and ZIP come from the beneficiary file
- each attending physician (by NPI) becomes a provider (PROV401 up), each hospital (by its
  NPI) a facility (FAC401 up). Physicians are grouped into departments by the ICD-10
  chapter of most of their principal diagnoses
- each claim becomes a Paid, institutional (inpatient, place of service 21) Medicare FFS
  claim with all its diagnoses; each revenue-center line a service line

What the files don't carry is filled in plainly, never guessed per claim: line charges are
the claim's total split evenly over its lines (CMS gives no line amounts), units are 1,
the submission date is the discharge date, and provider scores are a neutral 0.9. The
diagnosis and HCPCS code sets are extended with the codes the claims use, described from
CMS's own code files when given (CPT descriptions are AMA-licensed, so those stay as codes).
"""

import csv
import re
import shutil
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from app.sample_org import SHARED_TABLES

ORG_ID, ORG_NAME = "cms-florida", "Florida Medicare Inpatient (CMS synthetic)"
STATE = "10"  # SSA state code: Florida
MEDICARE = "PAY001"

# ICD-10-CM chapter (by first letter, or letter + digit) -> department
DEPARTMENTS = [
    ("DEPT81", "Cardiology", lambda c: c[0] == "I"),
    ("DEPT82", "Pulmonology", lambda c: c[0] == "J"),
    ("DEPT83", "Trauma & Orthopedics", lambda c: c[0] in "STM"),
    ("DEPT84", "Neurology & Behavioral Health", lambda c: c[0] in "FG"),
    ("DEPT85", "Oncology", lambda c: c[0] == "C" or (c[0] == "D" and c[1] in "01234")),
    ("DEPT86", "Gastroenterology", lambda c: c[0] == "K"),
    ("DEPT87", "Internal Medicine", lambda c: True),
]
BODY_SYSTEMS = {
    "A": "Infectious", "B": "Infectious", "C": "Neoplasms", "E": "Endocrine", "F": "Mental",
    "G": "Nervous", "H": "Eye and ear", "I": "Circulatory", "J": "Respiratory", "K": "Digestive",
    "L": "Skin", "M": "Musculoskeletal", "N": "Genitourinary", "O": "Pregnancy", "P": "Perinatal",
    "Q": "Congenital", "R": "Symptoms", "S": "Injury", "T": "Injury", "V": "External causes",
    "W": "External causes", "X": "External causes", "Y": "External causes", "Z": "Health status",
}
NEUTRAL_SCORE = 0.9


def convert(
    claims_csv: Path,
    beneficiaries_csv: Path,
    out_dir: Path,
    shared_from: Path,
    state: str = STATE,
    icd_descriptions: Path | None = None,
    hcpcs_descriptions: Path | None = None,
    today: date | None = None,
) -> dict[str, int]:
    """Write the organisation's tables to `out_dir`. Returns counts of what was written."""
    today = today or date.today()
    lines = pd.read_csv(claims_csv, sep="|", dtype=str, keep_default_na=False)
    lines = lines[lines["PRVDR_STATE_CD"] == state]
    if lines.empty:
        raise ValueError(f"No claims for state code {state} in {claims_csv}")
    for column in ("CLM_FROM_DT", "CLM_THRU_DT", "NCH_WKLY_PROC_DT"):
        lines[column] = pd.to_datetime(lines[column], format="%d-%b-%Y").dt.date
    lines = lines.sort_values(["CLM_FROM_DT", "CLM_ID", "CLM_LINE_NUM"], key=_line_order)
    claims = lines.drop_duplicates("CLM_ID").reset_index(drop=True)
    benes = pd.read_csv(beneficiaries_csv, sep="|", dtype=str, keep_default_na=False)
    benes = benes.drop_duplicates("BENE_ID", keep="last").set_index("BENE_ID")
    missing = set(claims["BENE_ID"]) - set(benes.index)
    if missing:
        raise ValueError(f"{len(missing)} beneficiaries in the claims aren't in {beneficiaries_csv}")

    out_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    for table in SHARED_TABLES:
        if table not in ("dim_cpt_codes", "dim_icd10_codes"):
            shutil.copyfile(shared_from / f"{table}.csv", out_dir / f"{table}.csv")

    # Patients
    patient_ids = {bene: f"PAT8{n:05d}" for n, bene in enumerate(dict.fromkeys(claims["BENE_ID"]), start=1)}
    patients = []
    for bene, patient_id in patient_ids.items():
        row = benes.loc[bene]
        born = datetime.strptime(row["BENE_BIRTH_DT"], "%d-%b-%Y").date()
        age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        patients.append((
            patient_id, "Beneficiary", bene.lstrip("-")[-8:], age,
            {"1": "M", "2": "F"}.get(row["SEX_IDENT_CD"], "U"), MEDICARE, 1.0,
            row["ZIP_CD"][:5], "Unknown", "Inactive" if row["BENE_DEATH_DT"].strip() else "Active",
        ))

    # Diagnoses (dotted, as the app stores them)
    dx_columns = [c for c in claims.columns if re.fullmatch(r"ICD_DGNS_CD\d+", c)]
    principal = claims["PRNCPAL_DGNS_CD"].map(_dotted)
    others = claims[dx_columns].apply(
        lambda row: [d for d in dict.fromkeys(_dotted(v) for v in row if v.strip())], axis=1
    )

    # Providers, departments by the chapter of most of their principal diagnoses
    department_of = {}
    for npi, codes in principal.groupby(claims["AT_PHYSN_NPI"]):
        chapter = Counter(_department(code) for code in codes).most_common(1)[0][0]
        department_of[npi] = chapter
    provider_ids = {npi: f"PROV{400 + n}" for n, npi in enumerate(sorted(department_of), start=1)}
    facility_ids = {npi: f"FAC{400 + n}" for n, npi in enumerate(sorted(set(claims["ORG_NPI_NUM"])), start=1)}
    if len(provider_ids) > 599 or len(facility_ids) > 599:
        raise ValueError("More than 599 physicians or hospitals: choose a smaller region")
    names = {dept: name for dept, name, _ in DEPARTMENTS}
    providers = [
        (pid, f"Attending physician {npi}", npi, names[department_of[npi]], department_of[npi],
         NEUTRAL_SCORE, NEUTRAL_SCORE, 0, "Active", "MD")
        for npi, pid in provider_ids.items()
    ]
    ccn = claims.groupby("ORG_NPI_NUM")["PRVDR_NUM"].first()
    facilities = [
        (fid, f"Hospital {npi} (CCN {ccn[npi]})", "Acute Care Hospital", 0, "", "Active", "")
        for npi, fid in facility_ids.items()
    ]

    # Claims
    claim_ids = {clm: f"CLM8{n:06d}" for n, clm in enumerate(claims["CLM_ID"], start=1)}
    claim_rows = []
    for i, row in claims.iterrows():
        paid = _money(row["CLM_PMT_AMT"])
        patient_share = sum(
            _money(row[c]) for c in ("NCH_BENE_IP_DDCTBL_AMT", "NCH_BENE_PTA_COINSRNC_LBLTY_AM", "NCH_BENE_BLOOD_DDCTBL_LBLTY_AM")
        )
        charge = _money(row["CLM_TOT_CHRG_AMT"])
        allowed = min(charge, round(paid + patient_share + _money(row["NCH_PRMRY_PYR_CLM_PD_AMT"]), 2))
        claim_rows.append((
            claim_ids[row["CLM_ID"]], patient_ids[row["BENE_ID"]], provider_ids[row["AT_PHYSN_NPI"]], MEDICARE,
            facility_ids[row["ORG_NPI_NUM"]], department_of[row["AT_PHYSN_NPI"]],
            row["CLM_FROM_DT"].isoformat(), row["CLM_THRU_DT"].isoformat(), charge, allowed, paid,
            round(patient_share, 2), "Paid", "Institutional", "21", principal[i],
            max(0, (row["NCH_WKLY_PROC_DT"] - row["CLM_THRU_DT"]).days), 1, 0, 0, "",
            "|".join(d for d in others[i] if d != principal[i]),
        ))

    # Lines: the claim's total charge, allowed and paid split evenly over its lines
    totals = {r[0]: r for r in claim_rows}
    line_rows, used_codes = [], Counter()
    for clm, group in lines.groupby("CLM_ID", sort=False):
        claim_id = claim_ids[clm]
        header = totals[claim_id]
        shares = _split_evenly(header[8], len(group)), _split_evenly(header[9], len(group)), _split_evenly(header[10], len(group))
        for n, (_, row) in enumerate(group.iterrows()):
            code = row["HCPCS_CD"].strip().upper()
            used_codes[code] += 1
            line_rows.append((
                f"LN8{len(line_rows) + 1:07d}", claim_id, int(row["CLM_LINE_NUM"]), code, _category(code), "", 1,
                shares[0][n], shares[1][n], shares[2][n], header[15], row["REV_CNTR"],
            ))

    # Departments, with their share of claims and daily volume
    by_department = Counter(r[5] for r in claim_rows)
    days = max(1, (claims["CLM_FROM_DT"].max() - claims["CLM_FROM_DT"].min()).days)
    departments = [
        (dept, name, "Inpatient", round(by_department[dept] / len(claim_rows), 3), 0.0,
         round(by_department[dept] / days))
        for dept, name, _ in DEPARTMENTS
        if by_department[dept]
    ]

    # Code sets: the shared ones plus every code these claims use
    _write_cpt(out_dir, shared_from, used_codes, line_rows, _hcpcs_names(hcpcs_descriptions))
    all_dx = Counter(d for codes in others for d in codes) + Counter(principal)
    _write_icd(out_dir, shared_from, all_dx, _icd_names(icd_descriptions))

    contracts = [r for r in _read(shared_from / "dim_payer_contracts.csv") if r["payer_id"] == MEDICARE]
    _write(out_dir / "dim_payer_contracts.csv", list(contracts[0]) if contracts else
           ["contract_id", "payer_id", "cpt_category", "reimbursement_pct_of_charge", "effective_date", "end_date", "status"],
           [list(r.values()) for r in contracts])
    _write(out_dir / "dim_patients.csv", ["patient_id", "first_name", "last_name", "age", "gender",
           "primary_payer_id", "risk_score", "zip_code", "language", "status"], patients)
    _write(out_dir / "dim_providers.csv", ["provider_id", "provider_name", "npi", "specialty", "department_id",
           "coding_accuracy_score", "documentation_completeness_score", "years_experience", "status", "credential"],
           providers)
    _write(out_dir / "dim_facilities.csv", ["facility_id", "facility_name", "facility_type", "bed_count",
           "address", "status", "tax_id"], facilities)
    _write(out_dir / "dim_departments.csv", ["department_id", "department_name", "service_line", "claim_share",
           "pa_frequency", "avg_daily_volume"], departments)
    _write(out_dir / "fact_claims.csv", ["claim_id", "patient_id", "provider_id", "payer_id", "facility_id",
           "department_id", "service_date", "submission_date", "total_charge", "total_allowed", "total_paid",
           "patient_responsibility", "status", "claim_type", "place_of_service", "primary_icd10", "days_in_ar",
           "is_clean_claim", "pa_required", "pa_obtained", "pa_number", "additional_icd10"], claim_rows)
    _write(out_dir / "fact_claim_lines.csv", ["line_id", "claim_id", "line_number", "cpt_code", "cpt_category",
           "modifier", "units", "charge_amount", "allowed_amount", "paid_amount", "icd10_pointer", "revenue_code"],
           line_rows)
    with (shared_from / "fact_denials.csv").open() as f:  # every claim in the file was paid
        (out_dir / "fact_denials.csv").write_text(f.readline())
    return {"claims": len(claim_rows), "lines": len(line_rows), "patients": len(patients),
            "providers": len(providers), "facilities": len(facilities), "departments": len(departments)}


def _line_order(column: pd.Series) -> pd.Series:
    return column.astype(int) if column.name == "CLM_LINE_NUM" else column


def _dotted(code: str) -> str:
    code = code.strip().upper()
    return f"{code[:3]}.{code[3:]}" if len(code) > 3 else code


def _department(code: str) -> str:
    return next(dept for dept, _, matches in DEPARTMENTS if matches(code))


def _money(value: str) -> float:
    return round(float(value), 2) if value.strip() else 0.0


def _split_evenly(total: float, parts: int) -> list[float]:
    """`total` in `parts` cent-exact shares (the first ones take any odd cents)."""
    cents = round(total * 100)
    base, extra = divmod(cents, parts)
    return [(base + (1 if n < extra else 0)) / 100 for n in range(parts)]


def _category(code: str) -> str:
    if code[0].isalpha():
        return "HCPCS"
    number = int(code)
    if 99202 <= number <= 99499:
        return "E&M"
    if 80000 <= number <= 89999:
        return "Lab"
    if 70000 <= number <= 79999:
        return "Radiology"
    if 90000 <= number <= 99199:
        return "Medicine"
    return "Surgery"


def _hcpcs_names(path: Path | None) -> dict[str, str]:
    """Short descriptions from CMS's alpha-numeric HCPCS file (fixed width)."""
    if path is None:
        return {}
    names = {}
    for line in path.read_text(encoding="latin-1").splitlines():
        if len(line) > 91 and line[10] == "3":  # the first record of each code
            names[line[:5].strip()] = line[91:119].strip()
    return names


def _icd_names(path: Path | None) -> dict[str, str]:
    """Descriptions from CMS's ICD-10-CM codes file ("A000    Cholera due to ...")."""
    if path is None:
        return {}
    names = {}
    for line in path.read_text(encoding="latin-1").splitlines():
        code, _, name = line.partition(" ")
        if code:
            names[_dotted(code)] = name.strip()
    return names


def _write_cpt(out_dir: Path, shared_from: Path, used: Counter, line_rows, names: dict[str, str]) -> None:
    rows = _read(shared_from / "dim_cpt_codes.csv")
    known = {r["cpt_code"] for r in rows}
    charges: dict[str, list[float]] = {}
    for row in line_rows:
        charges.setdefault(row[3], []).append(row[7])
    for code in sorted(set(used) - known):
        name = names.get(code) or (f"CPT {code}" if code[0].isdigit() else f"HCPCS {code}")
        average = round(sum(charges[code]) / len(charges[code]), 2)
        rows.append({"cpt_code": code, "description": name, "category": _category(code),
                     "standard_charge": average, "primary_department": "DEPT87", "billing_type": "Facility"})
    _write(out_dir / "dim_cpt_codes.csv", list(rows[0]), [list(r.values()) for r in rows])


def _write_icd(out_dir: Path, shared_from: Path, used: Counter, names: dict[str, str]) -> None:
    rows = _read(shared_from / "dim_icd10_codes.csv")
    known = {r["icd10_code"] for r in rows}
    total = sum(used.values())
    for code in sorted(set(used) - known):
        rows.append({"icd10_code": code, "description": names.get(code, f"ICD-10 {code}"),
                     "body_system": BODY_SYSTEMS.get(code[0], "Other"),
                     "relative_frequency": round(used[code] / total, 4), "acuity_type": "Both"})
    _write(out_dir / "dim_icd10_codes.csv", list(rows[0]), [list(r.values()) for r in rows])


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def _write(path: Path, header: list[str], rows) -> None:
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
