"""Building an organisation from CMS's synthetic Medicare inpatient claims (cms_org.py)."""

from datetime import date

from app import cms_org
from app.data.repository import ClaimsRepository
from app.tests.conftest import FIXTURES_DIR

CLAIM_COLUMNS = [
    "BENE_ID", "CLM_ID", "CLM_FROM_DT", "CLM_THRU_DT", "NCH_WKLY_PROC_DT", "PRVDR_NUM", "CLM_PMT_AMT",
    "NCH_PRMRY_PYR_CLM_PD_AMT", "PRVDR_STATE_CD", "ORG_NPI_NUM", "AT_PHYSN_NPI", "CLM_TOT_CHRG_AMT",
    "NCH_BENE_IP_DDCTBL_AMT", "NCH_BENE_PTA_COINSRNC_LBLTY_AM", "NCH_BENE_BLOOD_DDCTBL_LBLTY_AM",
    "PRNCPAL_DGNS_CD", "ICD_DGNS_CD1", "ICD_DGNS_CD2", "ICD_DGNS_CD3", "CLM_LINE_NUM", "REV_CNTR", "HCPCS_CD",
]
#            bene    claim  from          thru          processed     ccn       paid    prpy state org NPI       attending     charge  ddct  coins blood principal dx1     dx2     dx3     line rev    hcpcs
CLAIM_ROWS = [
    ["-1001", "-501", "05-Mar-2022", "08-Mar-2022", "11-Mar-2022", "100330", "900.00", "0", "10", "1000000010", "9999000001", "1000.00", "50.00", "40.00", "0", "I10", "I10", "E119", "", "1", "0450", "99213"],
    ["-1001", "-501", "05-Mar-2022", "08-Mar-2022", "11-Mar-2022", "100330", "900.00", "0", "10", "1000000010", "9999000001", "1000.00", "50.00", "40.00", "0", "I10", "I10", "E119", "", "2", "0450", "G0498"],
    ["-1001", "-501", "05-Mar-2022", "08-Mar-2022", "11-Mar-2022", "100330", "900.00", "0", "10", "1000000010", "9999000001", "1000.00", "50.00", "40.00", "0", "I10", "I10", "E119", "", "3", "0001", "99213"],
    ["-1002", "-502", "01-Feb-2021", "01-Feb-2021", "04-Feb-2021", "100410", "120.50", "0", "10", "1000000020", "9999000002", "120.50", "0", "24.10", "0", "S134XX", "S134XX", "R4689", "", "1", "0450", "99285"],
    # Another state: left out
    ["-1003", "-503", "01-Feb-2021", "01-Feb-2021", "04-Feb-2021", "050101", "99.00", "0", "05", "1000000030", "9999000003", "99.00", "0", "0", "0", "J189", "J189", "", "", "1", "0450", "99213"],
]
BENE_COLUMNS = ["BENE_ID", "ZIP_CD", "BENE_BIRTH_DT", "SEX_IDENT_CD", "BENE_DEATH_DT"]
BENE_ROWS = [
    ["-1001", "33101", "16-Aug-1950", "2", ""],
    ["-1002", "32223", "02-Jan-1940", "1", "03-Mar-2024"],
    ["-1003", "90001", "01-Jan-1955", "1", ""],
]


def write(path, columns, rows):
    path.write_text("\n".join("|".join(r) for r in [columns, *rows]) + "\n")
    return path


def convert(tmp_path, **options):
    claims = write(tmp_path / "inpatient.csv", CLAIM_COLUMNS, CLAIM_ROWS)
    benes = write(tmp_path / "beneficiary.csv", BENE_COLUMNS, BENE_ROWS)
    out = tmp_path / "org"
    counts = cms_org.convert(claims, benes, out, FIXTURES_DIR, today=date(2026, 1, 10), **options)
    return out, counts


def test_one_states_claims_become_the_organisations_tables(tmp_path):
    out, counts = convert(tmp_path)
    assert counts == {"claims": 2, "lines": 4, "patients": 2, "providers": 2, "facilities": 2, "departments": 2}
    repo = ClaimsRepository(out)
    first = repo.get_claim("CLM8000001")  # the earliest service date
    assert (first.patient_id, first.service_date.isoformat(), first.primary_icd10) == ("PAT800001", "2021-02-01", "S13.4XX")
    assert first.department_id == "DEPT83"  # Trauma & Orthopedics, from the S chapter
    claim = repo.get_claim("CLM8000002")
    assert (claim.status, claim.claim_type, claim.place_of_service, claim.payer_id) == ("Paid", "Institutional", "21", "PAY001")
    assert (claim.primary_icd10, claim.additional_icd10) == ("I10", ["E11.9"])
    assert (claim.service_date.isoformat(), claim.submission_date.isoformat(), claim.days_in_ar) == ("2022-03-05", "2022-03-08", 3)
    assert (claim.total_charge, claim.total_paid, claim.patient_responsibility, claim.total_allowed) == (1000.0, 900.0, 90.0, 990.0)
    # CMS gives no line amounts: the claim's total is split evenly, to the cent
    assert [(l.cpt_code, l.revenue_code, l.charge_amount) for l in claim.lines] == [
        ("99213", "0450", 333.34), ("G0498", "0450", 333.33), ("99213", "0001", 333.33)
    ]
    assert claim.patient.first_name == "Beneficiary" and claim.patient.gender == "F"
    assert repo.get_patient("PAT800001").status == "Inactive"  # died in 2024
    assert first.additional_icd10 == ["R46.89"]
    assert claim.provider.npi == "9999000001"


def test_codes_the_claims_use_join_the_code_sets(tmp_path):
    icd = tmp_path / "icd.txt"
    icd.write_text("E119    Type 2 diabetes mellitus without complications\nS134XX  Sprain of ligaments of cervical spine\n")
    hcpcs = tmp_path / "hcpcs.txt"
    hcpcs.write_text("G0498001003" + "Chemotherapy administration".ljust(80) + "Chemo extend iv infus w/pump\n")
    out, _ = convert(tmp_path, icd_descriptions=icd, hcpcs_descriptions=hcpcs)
    cpt = {r["cpt_code"]: r for r in cms_org._read(out / "dim_cpt_codes.csv")}
    assert cpt["G0498"]["description"] == "Chemo extend iv infus w/pump"
    assert cpt["G0498"]["category"] == "HCPCS"
    assert cpt["99285"]["description"] == "CPT 99285"  # CPT names are AMA-licensed
    icd10 = {r["icd10_code"]: r for r in cms_org._read(out / "dim_icd10_codes.csv")}
    assert icd10["S13.4XX"]["description"] == "Sprain of ligaments of cervical spine"
    assert icd10["S13.4XX"]["body_system"] == "Injury"
    assert icd10["R46.89"]["description"] == "ICD-10 R46.89"  # not in the file
    # Codes already in the shared set keep their entry
    shared = {r["icd10_code"]: r for r in cms_org._read(FIXTURES_DIR / "dim_icd10_codes.csv")}
    assert icd10["E11.9"] == shared["E11.9"]


def test_a_state_with_no_claims_is_refused(tmp_path):
    import pytest

    with pytest.raises(ValueError, match="No claims for state code 99"):
        convert(tmp_path, state="99")
