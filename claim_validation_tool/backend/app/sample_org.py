"""A second, synthetic organisation ("Lakeside Family Practice") for tests and demos.

It proves the organisation wall: a small family practice with its own patients,
providers, facility, departments, contracts, claims, and denials, all made up and
generated the same way every time (seeded). Its IDs use their own ranges (PAT9xxxxx,
CLM9xxxxxx, PROV9xx, DEPT9x, FAC9xx, CON9xxx) so a leak into another organisation is easy
to spot. Only the shared code sets (CPT, ICD-10, CARC/RARC, NCCI/MUE, LCD/NCD, fee
schedule) and the payer catalogue are copied from another organisation's data.
"""

import csv
import random
import shutil
from datetime import date, timedelta
from pathlib import Path

SHARED_TABLES = [
    "dim_cpt_codes", "dim_icd10_codes", "dim_payers", "ref_carc_codes", "ref_rarc_codes",
    "ref_lcd_ncd_policies", "ref_mue_limits", "ref_ncci_ptp_edits", "ref_physician_fee_schedule",
]

DEPARTMENTS = [
    ("DEPT91", "Family Medicine", "Primary Care", 0.6, 0.05, 30),
    ("DEPT92", "Pediatrics", "Pediatrics", 0.25, 0.03, 12),
    ("DEPT93", "Behavioral Health", "Behavioral Health", 0.15, 0.10, 8),
]
PROVIDERS = [
    ("PROV901", "Dr. Ellen Hartley", "Family Medicine", "DEPT91", "MD"),
    ("PROV902", "Dr. Samuel Okoro", "Family Medicine", "DEPT91", "DO"),
    ("PROV903", "Maria Lindqvist", "Family Medicine", "DEPT91", "NP"),
    ("PROV904", "Dr. Priya Raman", "Pediatrics", "DEPT92", "MD"),
    ("PROV905", "Dr. Thomas Byrne", "Pediatrics", "DEPT92", "MD"),
    ("PROV906", "Dr. Grace Whitfield", "Psychiatry", "DEPT93", "MD"),
]
FACILITY = ("FAC901", "Lakeside Family Practice", "Physician Office", 0,
            "18 Lakeshore Dr, Huntersville, NC 28078", "Active", "567891234")
# What each department bills, and the diagnoses that go with it
SERVICES = {
    "DEPT91": (["99213", "99214", "99215", "99203", "99204", "99396", "36415", "80053", "80061", "85025"],
               ["I10", "E11.9", "E78.5", "J06.9", "M54.5", "K21.0", "E11.65", "N39.0", "R10.9", "J45.20"]),
    "DEPT92": (["99213", "99214", "99381", "99391", "90471", "81001"],
               ["J06.9", "J45.20", "R10.9", "N39.0", "J18.9"]),
    "DEPT93": (["90834", "90837", "90847", "99214"],
               ["F32.1", "F41.1"]),
}
FIRST_NAMES = ["Avery", "Jordan", "Riley", "Morgan", "Casey", "Quinn", "Harper", "Rowan", "Elena",
               "Marcus", "Nia", "Owen", "Leah", "Mateo", "Imani", "Felix", "Sana", "Theo", "Mira",
               "Isaac", "Zara", "Luca", "Amara", "Ezra", "Hana", "Caleb", "Noor", "Silas"]
LAST_NAMES = ["Abernathy", "Blackwood", "Carrington", "Delacroix", "Ellsworth", "Fairbanks",
              "Galloway", "Hargreaves", "Iverson", "Kensington", "Langford", "Merriweather",
              "Northcott", "Oakley", "Pemberton", "Quayle", "Rutherford", "Sinclair", "Thornbury",
              "Underwood", "Vandermeer", "Whitlock", "Yardley", "Zeller"]
LANGUAGES = ["English", "English", "English", "Spanish", "Vietnamese", "Arabic"]
DENIALS = [
    ("Coding Errors", "16", "M76", "medical_coding", 1, "Coding Errors: Diagnosis missing or invalid"),
    ("Eligibility", "27", "N30", "eligibility_verification", 1, "Eligibility: Coverage terminated"),
    ("Prior Authorization", "197", "N54", "prior_authorization", 1, "Prior Authorization: Not obtained"),
    ("Medical Necessity", "50", "N115", "clinical_documentation", 0, "Medical Necessity: Not supported"),
    ("Duplicate", "18", "N522", "claim_submission", 1, "Duplicate: Claim already processed"),
]


def generate(out_dir: Path, shared_from: Path, patients: int = 300, claims: int = 1500) -> None:
    """Write Lakeside's CSVs to `out_dir`, copying the shared code sets from `shared_from`."""
    rng = random.Random(9001)
    out_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    for table in SHARED_TABLES:
        shutil.copyfile(shared_from / f"{table}.csv", out_dir / f"{table}.csv")
    cpt = {row["cpt_code"]: row for row in _read(shared_from / "dim_cpt_codes.csv")}
    known_dx = {row["icd10_code"] for row in _read(shared_from / "dim_icd10_codes.csv")}
    # Bill only what the copied code sets know (small test fixtures carry only a few codes)
    services = {
        dept: ([c for c in codes if c in cpt] or sorted(cpt)[:1], [d for d in dx if d in known_dx] or sorted(known_dx)[:1])
        for dept, (codes, dx) in SERVICES.items()
    }
    payers = [row for row in _read(shared_from / "dim_payers.csv")]
    insurers = [p["payer_id"] for p in payers if p["payer_type"] != "Self-Pay"]
    self_pay = next(p["payer_id"] for p in payers if p["payer_type"] == "Self-Pay")

    _write(out_dir / "dim_departments.csv",
           ["department_id", "department_name", "service_line", "claim_share", "pa_frequency", "avg_daily_volume"],
           DEPARTMENTS)
    _write(out_dir / "dim_providers.csv",
           ["provider_id", "provider_name", "npi", "specialty", "department_id", "coding_accuracy_score",
            "documentation_completeness_score", "years_experience", "status", "credential"],
           [(pid, name, f"19{rng.randrange(10**7, 10**8)}", spec, dept, round(rng.uniform(0.88, 0.99), 3),
             round(rng.uniform(0.8, 0.97), 3), rng.randrange(3, 28), "Active", cred)
            for pid, name, spec, dept, cred in PROVIDERS])
    _write(out_dir / "dim_facilities.csv",
           ["facility_id", "facility_name", "facility_type", "bed_count", "address", "status", "tax_id"], [FACILITY])
    _write(out_dir / "dim_payer_contracts.csv",
           ["contract_id", "payer_id", "cpt_category", "reimbursement_pct_of_charge", "effective_date", "end_date", "status"],
           [(f"CON9{n:03d}", payer_id, category, round(rng.uniform(0.55, 0.9), 3), "2025-01-01", "2025-12-31", "Active")
            for n, (payer_id, category) in enumerate(
                ((p, c) for p in insurers for c in ("E&M", "Lab", "Behavioral", "Preventive")), start=1)])

    people = []
    for n in range(1, patients + 1):
        age = rng.choice([rng.randrange(0, 18), rng.randrange(18, 65), rng.randrange(65, 95)])
        payer = self_pay if rng.random() < 0.06 else rng.choice(insurers)
        people.append((f"PAT9{n:05d}", rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES), age,
                       rng.choice("FM"), payer, round(rng.uniform(0.5, 3.5), 2),
                       rng.choice(["28078", "28031", "28036"]), rng.choice(LANGUAGES), "Active"))
    _write(out_dir / "dim_patients.csv",
           ["patient_id", "first_name", "last_name", "age", "gender", "primary_payer_id", "risk_score",
            "zip_code", "language", "status"], people)

    claim_rows, line_rows, denial_rows = [], [], []
    line_no = denial_no = 0
    start = date(2025, 1, 2)
    for n in range(1, claims + 1):
        patient = rng.choice(people)
        dept = "DEPT92" if patient[3] < 18 and rng.random() < 0.8 else rng.choices(
            ["DEPT91", "DEPT93"], weights=[0.8, 0.2])[0]
        provider = rng.choice([p for p in PROVIDERS if p[3] == dept])[0]
        codes, diagnoses = services[dept]
        service = start + timedelta(days=rng.randrange(0, 360))
        submitted = service + timedelta(days=rng.choice([1, 2, 3, 5, 8, 35]))
        primary = rng.choice(diagnoses)
        claim_id = f"CLM9{n:06d}"
        lines, total = [], 0.0
        for number, code in enumerate(rng.sample(codes, k=min(len(codes), rng.choice([1, 1, 2, 3]))), start=1):
            units = 1
            charge = float(cpt[code]["standard_charge"]) * units
            total += charge
            line_no += 1
            lines.append([f"LN9{line_no:07d}", claim_id, number, code, cpt[code]["category"],
                          "25" if code.startswith("992") and number > 1 else "", units, charge, 0.0, 0.0, primary])
        denied = rng.random() < 0.14
        allowed = 0.0 if denied else round(total * rng.uniform(0.6, 0.9), 2)
        paid = 0.0 if denied else round(allowed * rng.uniform(0.75, 1.0), 2)
        for line in lines:
            share = line[7] / total
            line[8], line[9] = round(allowed * share, 2), round(paid * share, 2)
        line_rows += lines
        pa_required = dept == "DEPT93" and rng.random() < 0.3
        pa_obtained = pa_required and rng.random() < 0.8
        days_in_ar = rng.randrange(5, 75)
        claim_rows.append((claim_id, patient[0], provider, patient[5], FACILITY[0], dept, service.isoformat(),
                           submitted.isoformat(), round(total, 2), allowed, paid, round(allowed - paid, 2),
                           "Denied" if denied else "Paid", "Professional", "11", primary, days_in_ar,
                           int(rng.random() > 0.25), int(pa_required), int(pa_obtained),
                           f"LKS{rng.randrange(10**5, 10**6)}" if pa_obtained else ""))
        if denied:
            denial_no += 1
            cause, carc, rarc, failure, preventable, text = rng.choice(DENIALS)
            days = rng.randrange(10, 45)
            denial_rows.append((f"DEN9{denial_no:06d}", claim_id, patient[5],
                                (submitted + timedelta(days=days)).isoformat(), cause, carc, rarc,
                                round(total, 2), failure, preventable, text, days))
    _write(out_dir / "fact_claims.csv",
           ["claim_id", "patient_id", "provider_id", "payer_id", "facility_id", "department_id", "service_date",
            "submission_date", "total_charge", "total_allowed", "total_paid", "patient_responsibility", "status",
            "claim_type", "place_of_service", "primary_icd10", "days_in_ar", "is_clean_claim", "pa_required",
            "pa_obtained", "pa_number"], claim_rows)
    _write(out_dir / "fact_claim_lines.csv",
           ["line_id", "claim_id", "line_number", "cpt_code", "cpt_category", "modifier", "units", "charge_amount",
            "allowed_amount", "paid_amount", "icd10_pointer"], line_rows)
    _write(out_dir / "fact_denials.csv",
           ["denial_id", "claim_id", "payer_id", "denial_date", "root_cause_category", "carc_code", "rarc_code",
            "denial_amount", "workflow_failure_point", "is_preventable", "denial_reason_text", "days_to_denial"],
           denial_rows)


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def _write(path: Path, header: list[str], rows) -> None:
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
