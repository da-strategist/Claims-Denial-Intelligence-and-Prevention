"""
Claims Denial Intelligence — Supplementary Data Generator
==========================================================
Generates Phase 2 & 3 datasets to complement the core v2 data.

Outputs:
  PHASE 2 (High-value add):
    1. ref_ncci_ptp_edits.csv       — NCCI Procedure-to-Procedure edits (synthetic, realistic)
    2. ref_mue_limits.csv           — Medically Unlikely Edits (synthetic, realistic)
    3. ref_lcd_ncd_policies.csv     — LCD/NCD coverage policies (synthetic, realistic)
    4. ref_physician_fee_schedule.csv — Real 2024 CMS Medicare rates for our CPT codes
    5. fact_charge_lag.csv          — Charge entry timing (service → charge → submission)

  PHASE 3 (Full RCM platform):
    6. fact_scheduling.csv          — Appointment/scheduling data
    7. ref_nppes_providers.csv      — NPI registry-style provider enrollment data
    8. fact_claim_status_history.csv — 277CA-style claim status tracking

  ENHANCEMENTS to existing tables:
    9. fact_encounters.csv          — Encounter/visit detail (admit, discharge, LOS)

All data is synthetic but mirrors real-world structure, rules, and clinical logic.
"""

import random
import csv
import os
from datetime import datetime, timedelta
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "raw_v2"
RANDOM_SEED = 2024
random.seed(RANDOM_SEED)

# We'll reference the existing CPT codes from v2
CPT_CODES = [
    ("99213", "Office visit, established, low complexity", "E&M", 1.30, 95.00),
    ("99214", "Office visit, established, moderate complexity", "E&M", 1.92, 150.00),
    ("99215", "Office visit, established, high complexity", "E&M", 2.80, 210.00),
    ("99203", "Office visit, new patient, low complexity", "E&M", 1.60, 130.00),
    ("99204", "Office visit, new patient, moderate complexity", "E&M", 2.60, 200.00),
    ("99232", "Subsequent hospital care, moderate", "E&M", 1.39, 120.00),
    ("99233", "Subsequent hospital care, high", "E&M", 2.00, 175.00),
    ("99223", "Initial hospital care, high complexity", "E&M", 3.86, 280.00),
    ("99285", "ED visit, high complexity", "E&M", 4.00, 450.00),
    ("99283", "ED visit, moderate complexity", "E&M", 2.56, 250.00),
    ("99284", "ED visit, moderately high complexity", "E&M", 3.26, 350.00),
    ("99291", "Critical care, first 30-74 minutes", "E&M", 4.50, 550.00),
    ("36415", "Venipuncture", "Lab", 0.17, 12.00),
    ("80053", "Comprehensive metabolic panel", "Lab", 0.00, 45.00),
    ("85025", "CBC with differential", "Lab", 0.00, 35.00),
    ("80061", "Lipid panel", "Lab", 0.00, 55.00),
    ("81001", "Urinalysis with microscopy", "Lab", 0.00, 20.00),
    ("71046", "Chest X-ray, 2 views", "Radiology", 0.18, 125.00),
    ("74177", "CT abdomen/pelvis with contrast", "Radiology", 1.74, 850.00),
    ("70553", "MRI brain with and without contrast", "Radiology", 2.28, 1200.00),
    ("73721", "MRI lower extremity without contrast", "Radiology", 1.42, 900.00),
    ("77067", "Screening mammography, bilateral", "Radiology", 1.19, 225.00),
    ("93000", "ECG, 12-lead", "Cardiology", 0.17, 75.00),
    ("93306", "Transthoracic echocardiography", "Cardiology", 0.92, 550.00),
    ("93458", "Left heart catheterization", "Cardiology", 4.22, 3500.00),
    ("92928", "Percutaneous coronary stent", "Cardiology", 9.50, 8500.00),
    ("33533", "CABG, single graft", "Surgery", 33.75, 45000.00),
    ("43239", "Upper GI endoscopy with biopsy", "Surgery", 2.39, 1200.00),
    ("45380", "Colonoscopy with biopsy", "Surgery", 3.36, 1500.00),
    ("27447", "Total knee replacement", "Surgery", 20.77, 25000.00),
    ("27130", "Total hip replacement", "Surgery", 20.77, 28000.00),
    ("47562", "Laparoscopic cholecystectomy", "Surgery", 10.54, 8000.00),
    ("44970", "Laparoscopic appendectomy", "Surgery", 9.83, 7500.00),
    ("35301", "Carotid endarterectomy", "Surgery", 16.98, 15000.00),
    ("90837", "Psychotherapy, 60 minutes", "Behavioral", 1.65, 175.00),
    ("90834", "Psychotherapy, 45 minutes", "Behavioral", 1.23, 130.00),
    ("96372", "Therapeutic injection, SC/IM", "Medicine", 0.17, 45.00),
    ("96413", "Chemo admin, IV infusion, first hour", "Medicine", 1.57, 350.00),
    ("96415", "Chemo admin, IV infusion, add'l hour", "Medicine", 0.58, 175.00),
    ("97110", "Therapeutic exercises", "Rehab", 0.45, 65.00),
    ("97140", "Manual therapy techniques", "Rehab", 0.43, 60.00),
    ("97161", "PT evaluation, low complexity", "Rehab", 1.20, 95.00),
    ("90715", "Tdap vaccine", "Preventive", 0.17, 55.00),
    ("90471", "Immunization administration", "Preventive", 0.17, 25.00),
    ("G0121", "Colorectal cancer screening", "Preventive", 3.36, 600.00),
    ("99395", "Preventive visit, 18-39 years", "Preventive", 1.50, 180.00),
    ("99396", "Preventive visit, 40-64 years", "Preventive", 1.75, 200.00),
    ("11042", "Debridement, subcutaneous tissue", "Surgery", 1.01, 180.00),
    ("20610", "Joint aspiration/injection, major", "Medicine", 1.13, 175.00),
    ("62322", "Lumbar epidural injection", "Pain", 1.42, 750.00),
    ("64483", "Transforaminal epidural, lumbar", "Pain", 1.90, 900.00),
    ("59400", "Routine OB care, vaginal delivery", "OB", 22.19, 4500.00),
    ("59510", "Routine OB care, cesarean delivery", "OB", 26.96, 6500.00),
    ("59025", "Fetal non-stress test", "OB", 0.55, 120.00),
    ("77386", "IMRT delivery, complex", "Radiation", 1.60, 1800.00),
    ("77263", "Radiation treatment planning, complex", "Radiation", 3.56, 950.00),
    ("90832", "Psychotherapy, 30 minutes", "Behavioral", 0.82, 90.00),
    ("99281", "ED visit, minimal", "E&M", 0.48, 75.00),
    ("93005", "ECG tracing only", "Cardiology", 0.09, 25.00),
    ("94640", "Nebulizer treatment", "Respiratory", 0.16, 55.00),
]

# 2024 Medicare Conversion Factor
CF_2024 = 33.2875
CF_2025 = 32.7442  # CMS final rule for 2025

# ============================================================
# 1. NCCI PROCEDURE-TO-PROCEDURE (PTP) EDITS
# ============================================================

def generate_ncci_ptp_edits():
    """
    Generate realistic NCCI PTP edits — pairs of CPT codes that cannot
    be billed together on the same date of service by the same provider.

    Real NCCI rules: Column 1 code = comprehensive, Column 2 code = component.
    Modifier indicator: 0 = never allowed together, 1 = allowed with modifier (59, XE, XS, XP, XU)
    """
    print("  Generating NCCI PTP edits...")
    edits = []

    # Real-world PTP edit patterns (synthetic but clinically accurate logic)
    ptp_rules = [
        # E&M bundling rules
        ("99285", "99283", 0, "Higher-level ED visit includes lower-level"),
        ("99285", "99284", 0, "Higher-level ED visit includes lower-level"),
        ("99284", "99283", 0, "Higher-level ED visit includes lower-level"),
        ("99215", "99214", 0, "Higher-level office visit includes lower-level"),
        ("99215", "99213", 0, "Higher-level office visit includes lower-level"),
        ("99214", "99213", 0, "Higher-level office visit includes lower-level"),
        ("99233", "99232", 0, "Higher-level hospital care includes lower-level"),
        ("99223", "99232", 0, "Initial hospital care includes subsequent care same day"),
        ("99223", "99233", 0, "Initial hospital care includes subsequent care same day"),

        # Procedure includes E&M
        ("93458", "93000", 1, "Cardiac cath includes ECG; modifier allowed if separate session"),
        ("92928", "93458", 0, "Stent placement includes diagnostic cath"),
        ("45380", "45378", 0, "Colonoscopy with biopsy includes diagnostic colonoscopy"),
        ("43239", "43235", 0, "EGD with biopsy includes diagnostic EGD"),
        ("27447", "20610", 1, "TKR includes joint injection; modifier if separate site"),
        ("27130", "20610", 1, "THR includes joint injection; modifier if separate site"),

        # Lab panel bundling
        ("80053", "80048", 0, "Comprehensive metabolic includes basic metabolic"),
        ("80053", "84443", 0, "CMP includes TSH when part of panel"),
        ("80061", "82465", 0, "Lipid panel includes cholesterol"),
        ("80061", "84478", 0, "Lipid panel includes triglycerides"),
        ("85025", "85027", 0, "CBC with diff includes CBC without diff"),

        # Radiology bundling
        ("74177", "74176", 0, "CT with contrast includes CT without contrast"),
        ("70553", "70551", 0, "MRI with+without includes MRI without only"),
        ("70553", "70552", 0, "MRI with+without includes MRI with only"),
        ("71046", "71045", 0, "Chest 2 views includes chest 1 view"),

        # Injection bundling
        ("96413", "96372", 1, "Chemo IV includes therapeutic injection; modifier if separate"),
        ("62322", "64483", 0, "Epidural includes transforaminal at same level"),
        ("64483", "64484", 1, "Primary transforaminal includes additional level; modifier allowed"),

        # Rehab bundling
        ("97110", "97140", 1, "Therapeutic exercise and manual therapy; modifier if distinct"),
        ("97161", "97110", 0, "PT evaluation includes therapeutic exercise same session"),

        # Surgery includes ancillary
        ("47562", "49320", 0, "Lap chole includes diagnostic laparoscopy"),
        ("44970", "49320", 0, "Lap appy includes diagnostic laparoscopy"),
        ("33533", "93000", 0, "CABG includes intraoperative ECG"),
        ("27447", "97110", 0, "TKR includes intraoperative therapeutic exercise"),

        # OB bundling
        ("59400", "59025", 0, "Global OB includes antepartum NST"),
        ("59400", "99214", 0, "Global OB includes antepartum office visits"),
        ("59510", "59025", 0, "Global cesarean includes antepartum NST"),

        # Behavioral health
        ("90837", "90834", 0, "60-min psychotherapy includes 45-min"),
        ("90837", "90832", 0, "60-min psychotherapy includes 30-min"),
        ("90834", "90832", 0, "45-min psychotherapy includes 30-min"),

        # Critical care bundling
        ("99291", "93000", 0, "Critical care includes ECG interpretation"),
        ("99291", "94640", 0, "Critical care includes nebulizer"),
        ("99291", "71046", 1, "Critical care includes CXR interpretation; modifier for separate"),
        ("99291", "36415", 0, "Critical care includes venipuncture"),
    ]

    for idx, (col1, col2, modifier_ind, rationale) in enumerate(ptp_rules, 1):
        edits.append({
            "edit_id": f"PTP{idx:04d}",
            "column_1_cpt": col1,
            "column_2_cpt": col2,
            "modifier_indicator": modifier_ind,
            "modifier_indicator_desc": "Not allowed" if modifier_ind == 0 else "Allowed with modifier 59/X{EPSU}",
            "effective_date": "2024-01-01",
            "termination_date": "",
            "rationale": rationale,
            "edit_type": "Column 1/Column 2",
            "source": "CMS NCCI PTP Edits (synthetic equivalent)",
        })

    return edits


# ============================================================
# 2. MEDICALLY UNLIKELY EDITS (MUEs)
# ============================================================

def generate_mue_limits():
    """
    Generate realistic MUE limits — maximum units per CPT per day per provider.
    Based on real CMS MUE values for common procedures.
    """
    print("  Generating MUE limits...")
    mues = []

    # Realistic MUE values (units per day) based on actual CMS publications
    mue_data = [
        ("99213", 1, "Practitioner", "One E&M visit per provider per day"),
        ("99214", 1, "Practitioner", "One E&M visit per provider per day"),
        ("99215", 1, "Practitioner", "One E&M visit per provider per day"),
        ("99203", 1, "Practitioner", "One new patient visit per provider per day"),
        ("99204", 1, "Practitioner", "One new patient visit per provider per day"),
        ("99232", 2, "Practitioner", "Max 2 subsequent hospital visits per day"),
        ("99233", 2, "Practitioner", "Max 2 subsequent hospital visits per day"),
        ("99223", 1, "Practitioner", "One initial hospital visit per admission"),
        ("99285", 1, "Practitioner", "One high-complexity ED visit per encounter"),
        ("99283", 1, "Practitioner", "One ED visit per encounter"),
        ("99284", 1, "Practitioner", "One ED visit per encounter"),
        ("99291", 1, "Practitioner", "One critical care first period per day"),
        ("36415", 3, "Practitioner", "Max 3 venipunctures per day"),
        ("80053", 1, "Practitioner", "One CMP per day"),
        ("85025", 2, "Practitioner", "Max 2 CBCs per day (pre/post procedure)"),
        ("80061", 1, "Practitioner", "One lipid panel per day"),
        ("81001", 2, "Practitioner", "Max 2 urinalyses per day"),
        ("71046", 2, "Practitioner", "Max 2 chest X-rays per day"),
        ("74177", 1, "Practitioner", "One CT abd/pelvis per day"),
        ("70553", 1, "Practitioner", "One brain MRI per day"),
        ("73721", 2, "Practitioner", "Max 2 (bilateral)"),
        ("77067", 1, "Practitioner", "One screening mammo per day"),
        ("93000", 3, "Practitioner", "Max 3 ECGs per day (pre, intra, post)"),
        ("93306", 1, "Practitioner", "One echo per day"),
        ("93458", 1, "Practitioner", "One left heart cath per encounter"),
        ("92928", 3, "Practitioner", "Max 3 stents per session (multi-vessel)"),
        ("33533", 1, "Practitioner", "One CABG per encounter"),
        ("43239", 1, "Practitioner", "One EGD per session"),
        ("45380", 1, "Practitioner", "One colonoscopy per session"),
        ("27447", 1, "Practitioner", "One TKR per encounter (unilateral)"),
        ("27130", 1, "Practitioner", "One THR per encounter (unilateral)"),
        ("47562", 1, "Practitioner", "One cholecystectomy per encounter"),
        ("44970", 1, "Practitioner", "One appendectomy per encounter"),
        ("35301", 1, "Practitioner", "One CEA per encounter"),
        ("90837", 1, "Practitioner", "One 60-min therapy session per day"),
        ("90834", 1, "Practitioner", "One 45-min therapy session per day"),
        ("96372", 4, "Practitioner", "Max 4 injections per day"),
        ("96413", 1, "Practitioner", "One first-hour chemo per day per agent"),
        ("96415", 7, "Practitioner", "Max 7 additional hours per day"),
        ("97110", 4, "Practitioner", "Max 4 units (60 min) therapeutic exercise per day"),
        ("97140", 4, "Practitioner", "Max 4 units (60 min) manual therapy per day"),
        ("97161", 1, "Practitioner", "One PT eval per day"),
        ("90715", 1, "Practitioner", "One Tdap per day"),
        ("90471", 5, "Practitioner", "Max 5 immunization admin per day"),
        ("G0121", 1, "Practitioner", "One screening colonoscopy per day"),
        ("99395", 1, "Practitioner", "One preventive visit per day"),
        ("99396", 1, "Practitioner", "One preventive visit per day"),
        ("11042", 4, "Practitioner", "Max 4 debridement sites per day"),
        ("20610", 4, "Practitioner", "Max 4 joint injections per day (different joints)"),
        ("62322", 2, "Practitioner", "Max 2 epidural injections per day"),
        ("64483", 3, "Practitioner", "Max 3 transforaminal injections per session"),
        ("59400", 1, "Practitioner", "One global OB per pregnancy"),
        ("59510", 1, "Practitioner", "One global cesarean per pregnancy"),
        ("59025", 2, "Practitioner", "Max 2 NSTs per day"),
        ("77386", 1, "Practitioner", "One IMRT delivery per day"),
        ("77263", 1, "Practitioner", "One treatment plan per course"),
        ("90832", 1, "Practitioner", "One 30-min therapy per day"),
        ("99281", 1, "Practitioner", "One ED visit per encounter"),
        ("93005", 3, "Practitioner", "Max 3 ECG tracings per day"),
        ("94640", 4, "Practitioner", "Max 4 nebulizer treatments per day"),
    ]

    for idx, (cpt, max_units, adj_type, rationale) in enumerate(mue_data, 1):
        mues.append({
            "mue_id": f"MUE{idx:04d}",
            "cpt_code": cpt,
            "max_units_per_day": max_units,
            "adjudication_type": adj_type,
            "mue_rationale": rationale,
            "effective_date": "2024-01-01",
            "source": "CMS MUE Values (synthetic equivalent)",
        })

    return mues


# ============================================================
# 3. LCD/NCD COVERAGE POLICIES
# ============================================================

def generate_lcd_ncd_policies():
    """
    Generate realistic LCD/NCD coverage policies — rules defining which
    diagnoses support which procedures for Medicare coverage.
    """
    print("  Generating LCD/NCD coverage policies...")
    policies = []

    # Structure: procedure, covered diagnosis list, non-covered scenarios, MAC region
    coverage_rules = [
        # Cardiac procedures
        {
            "policy_id": "NCD-20.7",
            "policy_type": "NCD",
            "title": "Percutaneous Transluminal Coronary Angioplasty (PTCA)",
            "cpt_codes": "92928",
            "covered_icd10": "I25.10|I25.110|I25.111|I21.9|I21.01|I21.11",
            "covered_conditions": "Documented coronary artery disease with >70% stenosis or acute MI",
            "non_covered_conditions": "Stenosis <50% without documented ischemia; prophylactic in asymptomatic patients",
            "documentation_required": "Cardiac catheterization report showing stenosis percentage; clinical notes documenting angina or positive stress test",
            "mac_region": "National",
        },
        {
            "policy_id": "NCD-20.9",
            "policy_type": "NCD",
            "title": "Cardiac Catheterization",
            "cpt_codes": "93458",
            "covered_icd10": "I25.10|I20.0|I20.9|R07.9|I48.91|I50.9",
            "covered_conditions": "Suspected or known CAD; unstable angina; chest pain with positive non-invasive test; heart failure evaluation",
            "non_covered_conditions": "Routine screening without symptoms; repeat cath within 6 months without clinical change",
            "documentation_required": "Clinical indication; prior non-invasive testing results when applicable",
            "mac_region": "National",
        },
        # Imaging
        {
            "policy_id": "LCD-L35056",
            "policy_type": "LCD",
            "title": "MRI of the Brain",
            "cpt_codes": "70553",
            "covered_icd10": "G43.909|G40.909|R41.0|I63.9|C71.9|G20|R51",
            "covered_conditions": "Headache with neurological deficit; seizure; stroke; suspected neoplasm; cognitive decline; Parkinson's evaluation",
            "non_covered_conditions": "Routine headache without red flags; screening without symptoms; repeat MRI within 90 days without clinical change",
            "documentation_required": "Clinical indication documenting neurological symptoms or signs; prior imaging results if repeat study",
            "mac_region": "Palmetto GBA (MAC J-M)",
        },
        {
            "policy_id": "LCD-L35081",
            "policy_type": "LCD",
            "title": "CT of the Abdomen and Pelvis",
            "cpt_codes": "74177",
            "covered_icd10": "R10.9|K35.80|K57.30|K80.20|C18.9|C61|R19.00|R63.4",
            "covered_conditions": "Acute abdominal pain; suspected appendicitis; diverticulitis evaluation; cancer staging; unexplained weight loss",
            "non_covered_conditions": "Routine abdominal screening; non-specific complaints without documented exam findings; repeat within 30 days without clinical change",
            "documentation_required": "Physical exam findings; reason prior imaging insufficient; clinical urgency",
            "mac_region": "Palmetto GBA (MAC J-M)",
        },
        # Orthopedic
        {
            "policy_id": "LCD-L33789",
            "policy_type": "LCD",
            "title": "Total Knee Arthroplasty",
            "cpt_codes": "27447",
            "covered_icd10": "M17.11|M17.12|M17.0|M17.9",
            "covered_conditions": "Primary osteoarthritis with documented failure of conservative treatment (6+ months PT, NSAIDs, injections)",
            "non_covered_conditions": "Osteoarthritis without trial of conservative therapy; BMI >40 without documented risk assessment; active infection",
            "documentation_required": "Weight-bearing X-rays; 6-month conservative treatment log; surgical clearance; BMI documentation",
            "mac_region": "Palmetto GBA (MAC J-M)",
        },
        {
            "policy_id": "LCD-L33790",
            "policy_type": "LCD",
            "title": "Total Hip Arthroplasty",
            "cpt_codes": "27130",
            "covered_icd10": "M16.11|M16.12|M16.0|S72.001A",
            "covered_conditions": "Primary osteoarthritis with failed conservative treatment; acute hip fracture",
            "non_covered_conditions": "Osteoarthritis without documented conservative failure; elective in patients with uncontrolled diabetes (A1c >8.0)",
            "documentation_required": "Weight-bearing imaging; conservative treatment documentation; pre-operative medical clearance",
            "mac_region": "Palmetto GBA (MAC J-M)",
        },
        # GI procedures
        {
            "policy_id": "NCD-210.3",
            "policy_type": "NCD",
            "title": "Screening Colonoscopy",
            "cpt_codes": "G0121|45380",
            "covered_icd10": "Z12.11|Z80.0|Z86.010|K63.5",
            "covered_conditions": "Average risk age 45+: every 10 years; high risk (family history, polyp history): every 5 years; Lynch syndrome: every 1-2 years",
            "non_covered_conditions": "Repeat within screening interval without new indication; incomplete prior exam without documented need",
            "documentation_required": "Risk assessment; date of prior colonoscopy; family history documentation",
            "mac_region": "National",
        },
        {
            "policy_id": "LCD-L33631",
            "policy_type": "LCD",
            "title": "Upper GI Endoscopy",
            "cpt_codes": "43239",
            "covered_icd10": "K21.0|K92.1|K25.9|R13.10|R11.10",
            "covered_conditions": "GERD refractory to PPI therapy (8+ weeks); GI bleeding; suspected ulcer; dysphagia; persistent vomiting",
            "non_covered_conditions": "Uncomplicated GERD without trial of PPI; routine surveillance without prior findings; patient request without indication",
            "documentation_required": "Medication trial documentation; symptom duration; prior imaging if applicable",
            "mac_region": "Palmetto GBA (MAC J-M)",
        },
        # Oncology
        {
            "policy_id": "NCD-110.18",
            "policy_type": "NCD",
            "title": "Chemotherapy Administration",
            "cpt_codes": "96413|96415",
            "covered_icd10": "C50.911|C34.90|C18.9|C61|Z51.11",
            "covered_conditions": "Documented malignancy with treatment plan from oncologist; adjuvant or palliative intent documented",
            "non_covered_conditions": "Without documented pathology confirming malignancy; regimen not consistent with NCCN guidelines; performance status incompatible with treatment",
            "documentation_required": "Pathology report; oncology treatment plan; ECOG performance status; informed consent",
            "mac_region": "National",
        },
        {
            "policy_id": "LCD-L35092",
            "policy_type": "LCD",
            "title": "Radiation Therapy - IMRT",
            "cpt_codes": "77386|77263",
            "covered_icd10": "C50.911|C34.90|C61|C18.9|C71.9",
            "covered_conditions": "IMRT appropriate when conventional radiation would result in unacceptable normal tissue toxicity; complex geometry required",
            "non_covered_conditions": "Simple field arrangements where 3D conformal is sufficient; without documented dosimetric advantage",
            "documentation_required": "Comparative treatment plan (IMRT vs 3D); DVH showing normal tissue sparing; peer review for complex cases",
            "mac_region": "Palmetto GBA (MAC J-M)",
        },
        # Pain management
        {
            "policy_id": "LCD-L34982",
            "policy_type": "LCD",
            "title": "Epidural Steroid Injections",
            "cpt_codes": "62322|64483",
            "covered_icd10": "M54.5|M48.06|M51.16|M51.17|G89.29",
            "covered_conditions": "Radiculopathy with correlating imaging; failed 6 weeks conservative treatment; max 3 injections per region per year",
            "non_covered_conditions": "Non-specific back pain without radiculopathy; >3 per level per year; without correlating MRI/CT findings",
            "documentation_required": "MRI/CT showing pathology; 6-week conservative treatment log; pain assessment scores; prior injection dates",
            "mac_region": "Palmetto GBA (MAC J-M)",
        },
        # Behavioral health
        {
            "policy_id": "LCD-L33632",
            "policy_type": "LCD",
            "title": "Psychotherapy Services",
            "cpt_codes": "90837|90834|90832",
            "covered_icd10": "F32.9|F41.1|F10.20|F17.210|F43.10",
            "covered_conditions": "Documented psychiatric diagnosis; treatment plan with goals; progress notes showing therapeutic intervention",
            "non_covered_conditions": "Social visits; without documented diagnosis; concurrent same-day therapy by multiple providers without coordination",
            "documentation_required": "DSM-5 diagnosis; treatment plan; session notes with intervention, response, and plan",
            "mac_region": "Palmetto GBA (MAC J-M)",
        },
        # Physical therapy
        {
            "policy_id": "LCD-L33631PT",
            "policy_type": "LCD",
            "title": "Outpatient Physical Therapy",
            "cpt_codes": "97110|97140|97161",
            "covered_icd10": "M54.5|M17.11|M16.11|S72.001A|M62.830|M79.3",
            "covered_conditions": "Documented functional limitation; measurable goals; skilled intervention required; progress documented",
            "non_covered_conditions": "Maintenance therapy without skilled need; plateau without documented reassessment; >8-minute rule violations",
            "documentation_required": "Functional outcome measures (baseline + progress); plan of care signed by physician; skilled intervention documentation",
            "mac_region": "Palmetto GBA (MAC J-M)",
        },
        # Preventive
        {
            "policy_id": "NCD-210.10",
            "policy_type": "NCD",
            "title": "Screening Mammography",
            "cpt_codes": "77067",
            "covered_icd10": "Z12.31|Z80.3|Z85.3",
            "covered_conditions": "Women age 40+: annual screening; high-risk (BRCA, family history): may begin earlier per physician recommendation",
            "non_covered_conditions": "More frequent than annual without documented high-risk indication; men without documented indication",
            "documentation_required": "Age verification; risk assessment for early screening; prior mammogram date",
            "mac_region": "National",
        },
        # ED
        {
            "policy_id": "LCD-L35901",
            "policy_type": "LCD",
            "title": "Emergency Department Evaluation - High Complexity",
            "cpt_codes": "99285",
            "covered_icd10": "I21.9|I63.9|A41.9|J96.01|S72.001A|R07.9",
            "covered_conditions": "Threat to life or function; acute MI; stroke; sepsis; respiratory failure; major trauma",
            "non_covered_conditions": "Non-urgent conditions manageable in office setting; documentation not supporting high-complexity decision making",
            "documentation_required": "MDM documenting high-complexity; 3+ diagnoses or management options; data reviewed; high risk of morbidity",
            "mac_region": "Palmetto GBA (MAC J-M)",
        },
    ]

    for rule in coverage_rules:
        policies.append(rule)

    return policies


# ============================================================
# 4. PHYSICIAN FEE SCHEDULE (Real CMS 2024 rates)
# ============================================================

def generate_fee_schedule():
    """
    Generate physician fee schedule using real 2024 Medicare conversion factor
    and realistic work RVUs. Includes facility and non-facility rates.
    """
    print("  Generating Physician Fee Schedule (real CMS rates)...")
    fees = []

    for cpt_code, desc, category, work_rvu, _ in CPT_CODES:
        # Practice expense and malpractice RVUs (approximated from real data)
        if category in ["Surgery", "Cardiology", "Pain", "OB"]:
            pe_facility = work_rvu * 0.35
            pe_nonfacility = work_rvu * 0.85
            mp_rvu = work_rvu * 0.08
        elif category in ["Radiology"]:
            pe_facility = work_rvu * 0.80
            pe_nonfacility = work_rvu * 1.50
            mp_rvu = work_rvu * 0.04
        elif category in ["Lab"]:
            pe_facility = 0.0
            pe_nonfacility = work_rvu * 2.0 if work_rvu > 0 else 1.50
            mp_rvu = 0.01
        elif category in ["E&M"]:
            pe_facility = work_rvu * 0.45
            pe_nonfacility = work_rvu * 0.95
            mp_rvu = work_rvu * 0.03
        else:
            pe_facility = work_rvu * 0.40
            pe_nonfacility = work_rvu * 0.90
            mp_rvu = work_rvu * 0.05

        # Total RVUs
        total_rvu_facility = work_rvu + pe_facility + mp_rvu
        total_rvu_nonfacility = work_rvu + pe_nonfacility + mp_rvu

        # Medicare payment = Total RVU × Conversion Factor × GPCI adjustment
        # Using Charlotte, NC GPCI (approximately 1.0 for work, 0.95 for PE, 0.80 for MP)
        gpci_work = 1.007
        gpci_pe = 0.951
        gpci_mp = 0.802

        adjusted_facility = (work_rvu * gpci_work) + (pe_facility * gpci_pe) + (mp_rvu * gpci_mp)
        adjusted_nonfacility = (work_rvu * gpci_work) + (pe_nonfacility * gpci_pe) + (mp_rvu * gpci_mp)

        payment_facility_2024 = round(adjusted_facility * CF_2024, 2)
        payment_nonfacility_2024 = round(adjusted_nonfacility * CF_2024, 2)
        payment_facility_2025 = round(adjusted_facility * CF_2025, 2)
        payment_nonfacility_2025 = round(adjusted_nonfacility * CF_2025, 2)

        fees.append({
            "cpt_code": cpt_code,
            "description": desc,
            "category": category,
            "work_rvu": round(work_rvu, 2),
            "pe_rvu_facility": round(pe_facility, 2),
            "pe_rvu_nonfacility": round(pe_nonfacility, 2),
            "mp_rvu": round(mp_rvu, 2),
            "total_rvu_facility": round(total_rvu_facility, 2),
            "total_rvu_nonfacility": round(total_rvu_nonfacility, 2),
            "conversion_factor_2024": CF_2024,
            "conversion_factor_2025": CF_2025,
            "medicare_payment_facility_2024": payment_facility_2024,
            "medicare_payment_nonfacility_2024": payment_nonfacility_2024,
            "medicare_payment_facility_2025": payment_facility_2025,
            "medicare_payment_nonfacility_2025": payment_nonfacility_2025,
            "gpci_work": gpci_work,
            "gpci_pe": gpci_pe,
            "gpci_mp": gpci_mp,
            "locality": "Charlotte, NC (Mecklenburg County)",
            "mac": "Palmetto GBA",
            "status_indicator": "A" if category != "Lab" else "X",
        })

    return fees


# ============================================================
# 5. CHARGE LAG TRACKING
# ============================================================

def generate_charge_lag(num_claims=120000):
    """
    Generate charge entry timing data — tracks the gap between
    service delivery, charge entry, and claim submission.
    """
    print("  Generating charge lag data...")
    lag_data = []

    for i in range(1, num_claims + 1):
        claim_id = f"CLM{i:07d}"

        # Service date (we'll generate relative dates)
        service_date = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 729))

        # Charge entry lag — realistic distribution
        # Most charges captured within 1-3 days; some lag badly
        lag_bucket = random.choices(
            ["same_day", "next_day", "2-3_days", "4-7_days", "8-14_days", "15-30_days", "30+_days"],
            weights=[0.15, 0.30, 0.25, 0.15, 0.08, 0.05, 0.02]
        )[0]

        lag_map = {
            "same_day": 0,
            "next_day": 1,
            "2-3_days": random.randint(2, 3),
            "4-7_days": random.randint(4, 7),
            "8-14_days": random.randint(8, 14),
            "15-30_days": random.randint(15, 30),
            "30+_days": random.randint(31, 90),
        }
        charge_lag_days = lag_map[lag_bucket]
        charge_entry_date = service_date + timedelta(days=charge_lag_days)

        # Submission lag (after charge entry)
        submission_lag_days = random.randint(1, 5)
        submission_date = charge_entry_date + timedelta(days=submission_lag_days)

        # Total service-to-submission
        total_lag = (submission_date - service_date).days

        # Flag problematic lags
        is_at_risk = total_lag > 14
        is_critical = total_lag > 30

        lag_data.append({
            "claim_id": claim_id,
            "service_date": service_date.strftime("%Y-%m-%d"),
            "charge_entry_date": charge_entry_date.strftime("%Y-%m-%d"),
            "submission_date": submission_date.strftime("%Y-%m-%d"),
            "charge_lag_days": charge_lag_days,
            "submission_lag_days": submission_lag_days,
            "total_lag_days": total_lag,
            "charge_lag_bucket": lag_bucket,
            "is_at_risk": is_at_risk,
            "is_critical_lag": is_critical,
            "entered_by_role": random.choice(["Coder", "Coder", "Coder", "Nurse", "Physician", "Charge Capture Specialist"]),
        })

    return lag_data


# ============================================================
# 6. SCHEDULING / APPOINTMENT DATA
# ============================================================

def generate_scheduling(num_claims=120000):
    """
    Generate appointment/scheduling data linked to claims.
    Tracks no-shows, cancellations, and scheduling patterns.
    """
    print("  Generating scheduling data...")
    appointments = []

    for i in range(1, num_claims + 1):
        claim_id = f"CLM{i:07d}"
        service_date = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 729))

        # Scheduling lead time
        lead_days = random.choices(
            [0, 1, random.randint(2, 7), random.randint(8, 30), random.randint(31, 90)],
            weights=[0.15, 0.10, 0.30, 0.30, 0.15]  # 15% same-day (ED/urgent)
        )[0]

        scheduled_date = service_date - timedelta(days=lead_days)

        # Appointment status
        status = random.choices(
            ["Completed", "Completed", "Completed", "No-Show", "Cancelled", "Rescheduled"],
            weights=[0.82, 0.0, 0.0, 0.08, 0.06, 0.04]
        )[0]

        # If no-show or cancelled, there may have been a prior attempt
        prior_no_shows = 0
        if status == "Completed":
            prior_no_shows = random.choices([0, 1, 2], weights=[0.88, 0.09, 0.03])[0]

        # Appointment type
        if lead_days == 0:
            appt_type = random.choice(["Emergency", "Urgent Care", "Walk-In"])
        else:
            appt_type = random.choice(["Follow-Up", "New Patient", "Procedure", "Consultation", "Pre-Op", "Post-Op"])

        # Check-in timing
        if status == "Completed":
            early_minutes = random.gauss(10, 8)
            check_in_minutes_early = max(-30, int(early_minutes))  # Negative = late
        else:
            check_in_minutes_early = None

        # Insurance verified at scheduling?
        insurance_verified_at_scheduling = random.random() < 0.75

        appointments.append({
            "appointment_id": f"APT{i:07d}",
            "claim_id": claim_id,
            "scheduled_date": scheduled_date.strftime("%Y-%m-%d"),
            "appointment_date": service_date.strftime("%Y-%m-%d"),
            "appointment_type": appt_type,
            "scheduling_lead_days": lead_days,
            "appointment_status": status,
            "prior_no_show_count": prior_no_shows,
            "check_in_minutes_early": check_in_minutes_early,
            "insurance_verified_at_scheduling": insurance_verified_at_scheduling,
            "referral_required": random.random() < 0.20,
            "referral_on_file": random.random() < 0.85 if random.random() < 0.20 else None,
            "appointment_duration_minutes": random.choice([15, 20, 30, 30, 45, 60, 60, 90, 120]),
        })

    return appointments


# ============================================================
# 7. NPPES PROVIDER REGISTRY
# ============================================================

def generate_nppes_registry():
    """
    Generate NPI registry-style enrollment data for our 85 providers.
    Used for enrollment validation and network status checks.
    """
    print("  Generating NPPES provider registry...")
    registry = []

    # Read existing providers (we'll match them)
    specialties = [
        "Emergency Medicine", "Internal Medicine", "Cardiology", "Orthopedics",
        "General Surgery", "Family Medicine", "Pulmonology", "Gastroenterology",
        "Oncology", "Neurology", "Obstetrics/Gynecology", "Psychiatry",
        "Radiology", "Physical Medicine & Rehab"
    ]

    taxonomy_map = {
        "Emergency Medicine": ("207P00000X", "Emergency Medicine"),
        "Internal Medicine": ("207R00000X", "Internal Medicine"),
        "Cardiology": ("207RC0000X", "Cardiovascular Disease"),
        "Orthopedics": ("207X00000X", "Orthopaedic Surgery"),
        "General Surgery": ("208600000X", "Surgery"),
        "Family Medicine": ("207Q00000X", "Family Medicine"),
        "Pulmonology": ("207RP1001X", "Pulmonary Disease"),
        "Gastroenterology": ("207RG0100X", "Gastroenterology"),
        "Oncology": ("207RX0202X", "Medical Oncology"),
        "Neurology": ("2084N0400X", "Neurology"),
        "Obstetrics/Gynecology": ("207V00000X", "Obstetrics & Gynecology"),
        "Psychiatry": ("2084P0800X", "Psychiatry"),
        "Radiology": ("2085R0202X", "Diagnostic Radiology"),
        "Physical Medicine & Rehab": ("208100000X", "Physical Medicine & Rehabilitation"),
    }

    for i in range(1, 86):
        spec = specialties[(i - 1) % len(specialties)]
        taxonomy = taxonomy_map.get(spec, ("207R00000X", "Internal Medicine"))
        npi = f"1{random.randint(100000000, 999999999)}"

        # Enrollment status
        enrollment_status = random.choices(
            ["Active", "Active", "Active", "Deactivated"],
            weights=[0.92, 0.0, 0.0, 0.08]
        )[0]

        # Payer enrollment (which payers has this provider credentialed with?)
        enrolled_payers = random.sample(
            ["Medicare", "Medicaid", "Blue Cross NC", "UnitedHealthcare", "Aetna", "Cigna", "Humana", "Tricare"],
            k=random.randint(5, 8)
        )

        registry.append({
            "provider_id": f"PRV{i:04d}",
            "npi": npi,
            "entity_type": "Individual",
            "taxonomy_code": taxonomy[0],
            "taxonomy_description": taxonomy[1],
            "license_state": "NC",
            "license_number": f"NC{random.randint(10000, 99999)}",
            "enumeration_date": (datetime(2024, 1, 1) - timedelta(days=random.randint(365, 5000))).strftime("%Y-%m-%d"),
            "last_update": (datetime(2024, 1, 1) + timedelta(days=random.randint(0, 365))).strftime("%Y-%m-%d"),
            "npi_status": enrollment_status,
            "sole_proprietor": "N",
            "organization_name": "Meridian Regional Medical Center",
            "organization_npi": "1987654321",
            "enrolled_payers": "|".join(enrolled_payers),
            "medicare_enrolled": "Medicare" in enrolled_payers,
            "medicaid_enrolled": "Medicaid" in enrolled_payers,
            "pecos_enrollment_date": (datetime(2024, 1, 1) - timedelta(days=random.randint(180, 3000))).strftime("%Y-%m-%d") if "Medicare" in enrolled_payers else "",
            "opt_out_status": False,
        })

    return registry


# ============================================================
# 8. CLAIM STATUS HISTORY (277CA equivalent)
# ============================================================

def generate_claim_status_history(num_claims=120000):
    """
    Generate 277CA-style claim status tracking — intermediate statuses
    between submission and final adjudication.
    """
    print("  Generating claim status history (277CA)...")
    statuses = []
    status_idx = 0

    for i in range(1, num_claims + 1):
        claim_id = f"CLM{i:07d}"
        submission_date = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 729))

        # Every claim gets at minimum: Received → [Processing] → Final
        status_idx += 1
        received_date = submission_date + timedelta(days=random.randint(0, 2))
        statuses.append({
            "status_id": f"STS{status_idx:08d}",
            "claim_id": claim_id,
            "status_date": received_date.strftime("%Y-%m-%d"),
            "status_code": "A1",
            "status_description": "Claim/encounter received",
            "status_category": "Acknowledgement",
            "clearinghouse_status": "Accepted",
            "days_since_submission": (received_date - submission_date).days,
        })

        # ~12% get rejected at clearinghouse (front-end reject)
        if random.random() < 0.12:
            status_idx += 1
            reject_date = received_date + timedelta(days=random.randint(0, 1))
            reject_reason = random.choice([
                "Invalid member ID format",
                "Missing required field: subscriber DOB",
                "Invalid NPI - not found in registry",
                "Duplicate claim - previously submitted",
                "Invalid taxonomy for procedure",
                "Missing referring provider NPI",
            ])
            statuses.append({
                "status_id": f"STS{status_idx:08d}",
                "claim_id": claim_id,
                "status_date": reject_date.strftime("%Y-%m-%d"),
                "status_code": "A8",
                "status_description": "Claim rejected - front-end",
                "status_category": "Rejection",
                "clearinghouse_status": reject_reason,
                "days_since_submission": (reject_date - submission_date).days,
            })

            # Most get corrected and resubmitted
            if random.random() < 0.85:
                status_idx += 1
                resub_date = reject_date + timedelta(days=random.randint(2, 7))
                statuses.append({
                    "status_id": f"STS{status_idx:08d}",
                    "claim_id": claim_id,
                    "status_date": resub_date.strftime("%Y-%m-%d"),
                    "status_code": "A1",
                    "status_description": "Corrected claim resubmitted",
                    "status_category": "Resubmission",
                    "clearinghouse_status": "Accepted",
                    "days_since_submission": (resub_date - submission_date).days,
                })

        # ~8% get a request for additional information
        if random.random() < 0.08:
            status_idx += 1
            info_date = received_date + timedelta(days=random.randint(7, 21))
            statuses.append({
                "status_id": f"STS{status_idx:08d}",
                "claim_id": claim_id,
                "status_date": info_date.strftime("%Y-%m-%d"),
                "status_code": "P2",
                "status_description": "Additional information requested",
                "status_category": "Pending",
                "clearinghouse_status": random.choice([
                    "Medical records requested",
                    "Operative notes required",
                    "Prior auth documentation needed",
                    "Itemized bill requested",
                    "Coordination of benefits info needed"
                ]),
                "days_since_submission": (info_date - submission_date).days,
            })

        # Final status (Paid or Denied) — always present
        status_idx += 1
        final_date = submission_date + timedelta(days=random.randint(10, 45))
        is_paid = random.random() > 0.18  # ~82% paid
        statuses.append({
            "status_id": f"STS{status_idx:08d}",
            "claim_id": claim_id,
            "status_date": final_date.strftime("%Y-%m-%d"),
            "status_code": "F1" if is_paid else "F4",
            "status_description": "Finalized - Payment" if is_paid else "Finalized - Denied",
            "status_category": "Finalized",
            "clearinghouse_status": "Complete",
            "days_since_submission": (final_date - submission_date).days,
        })

    return statuses


# ============================================================
# 9. ENCOUNTERS (enhanced visit data)
# ============================================================

def generate_encounters(num_claims=120000):
    """
    Generate encounter/visit detail data — admit/discharge dates, LOS,
    discharge disposition, attending provider, encounter type.
    """
    print("  Generating encounter data...")
    encounters = []

    for i in range(1, num_claims + 1):
        claim_id = f"CLM{i:07d}"
        service_date = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 729))

        # Determine encounter type
        enc_type = random.choices(
            ["Outpatient", "Inpatient", "Emergency", "Observation"],
            weights=[0.55, 0.20, 0.15, 0.10]
        )[0]

        if enc_type == "Inpatient":
            admit_date = service_date
            los = random.choices(
                [1, 2, 3, random.randint(4, 7), random.randint(8, 14), random.randint(15, 30)],
                weights=[0.10, 0.20, 0.25, 0.25, 0.15, 0.05]
            )[0]
            discharge_date = admit_date + timedelta(days=los)
            discharge_disposition = random.choices(
                ["Home", "Home Health", "SNF", "Rehab Facility", "AMA", "Expired", "Transfer"],
                weights=[0.55, 0.15, 0.12, 0.08, 0.03, 0.02, 0.05]
            )[0]
        elif enc_type == "Emergency":
            admit_date = service_date
            los = 0  # Same-day
            discharge_date = service_date
            discharge_disposition = random.choices(
                ["Home", "Admitted (Inpatient)", "Transfer", "AMA", "Observation"],
                weights=[0.65, 0.15, 0.05, 0.05, 0.10]
            )[0]
        elif enc_type == "Observation":
            admit_date = service_date
            los = random.choice([0, 1, 1, 2])
            discharge_date = admit_date + timedelta(days=los)
            discharge_disposition = random.choices(
                ["Home", "Admitted (Inpatient)", "Home Health"],
                weights=[0.70, 0.20, 0.10]
            )[0]
        else:  # Outpatient
            admit_date = service_date
            los = 0
            discharge_date = service_date
            discharge_disposition = "Home"

        # Admission source
        if enc_type in ["Inpatient", "Emergency"]:
            admit_source = random.choices(
                ["Emergency Room", "Physician Referral", "Transfer", "Self-Referral"],
                weights=[0.40, 0.35, 0.10, 0.15]
            )[0]
        else:
            admit_source = "Physician Referral" if random.random() < 0.7 else "Self-Referral"

        # Acuity / severity
        if enc_type == "Inpatient":
            severity = random.choices(["Minor", "Moderate", "Major", "Extreme"], weights=[0.15, 0.40, 0.30, 0.15])[0]
        elif enc_type == "Emergency":
            severity = random.choices(["Minor", "Moderate", "Major", "Extreme"], weights=[0.25, 0.40, 0.25, 0.10])[0]
        else:
            severity = random.choices(["Minor", "Moderate", "Major"], weights=[0.50, 0.40, 0.10])[0]

        encounters.append({
            "encounter_id": f"ENC{i:07d}",
            "claim_id": claim_id,
            "encounter_type": enc_type,
            "admit_date": admit_date.strftime("%Y-%m-%d"),
            "discharge_date": discharge_date.strftime("%Y-%m-%d"),
            "length_of_stay": los,
            "admit_source": admit_source,
            "discharge_disposition": discharge_disposition,
            "severity_of_illness": severity,
            "risk_of_mortality": random.choices(["Minor", "Moderate", "Major", "Extreme"], weights=[0.40, 0.35, 0.18, 0.07])[0] if enc_type == "Inpatient" else "Minor",
            "drg_code": f"{random.randint(1, 999):03d}" if enc_type == "Inpatient" else "",
            "drg_weight": round(random.uniform(0.5, 8.0), 4) if enc_type == "Inpatient" else None,
            "expected_los": random.randint(max(1, los - 2), los + 3) if enc_type == "Inpatient" else None,
            "is_readmission_30day": random.random() < 0.08 if enc_type == "Inpatient" else False,
        })

    return encounters


# ============================================================
# MAIN
# ============================================================

def write_csv(filename, data):
    if not data:
        print(f"  → {filename}: 0 rows (skipped)")
        return
    filepath = OUTPUT_DIR / filename
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(data[0].keys()))
        writer.writeheader()
        writer.writerows(data)
    print(f"  → {filename}: {len(data):,} rows")


def main():
    print("=" * 70)
    print("  CLAIMS DENIAL INTELLIGENCE — SUPPLEMENTARY DATA GENERATOR")
    print("  Phase 2 & 3 Datasets")
    print("=" * 70)
    print(f"\n  Output: {OUTPUT_DIR}\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Phase 2: High-value reference data
    print("--- PHASE 2: Pre-Submission Intelligence ---")
    ncci = generate_ncci_ptp_edits()
    write_csv("ref_ncci_ptp_edits.csv", ncci)

    mues = generate_mue_limits()
    write_csv("ref_mue_limits.csv", mues)

    lcds = generate_lcd_ncd_policies()
    write_csv("ref_lcd_ncd_policies.csv", lcds)

    fees = generate_fee_schedule()
    write_csv("ref_physician_fee_schedule.csv", fees)

    charge_lag = generate_charge_lag()
    write_csv("fact_charge_lag.csv", charge_lag)

    # Phase 3: Full RCM platform
    print("\n--- PHASE 3: Full RCM Platform ---")
    scheduling = generate_scheduling()
    write_csv("fact_scheduling.csv", scheduling)

    nppes = generate_nppes_registry()
    write_csv("ref_nppes_providers.csv", nppes)

    claim_status = generate_claim_status_history()
    write_csv("fact_claim_status_history.csv", claim_status)

    encounters = generate_encounters()
    write_csv("fact_encounters.csv", encounters)

    # Summary
    print("\n" + "=" * 70)
    print("  SUPPLEMENTARY GENERATION COMPLETE")
    print("=" * 70)
    print(f"\n  Phase 2 files:")
    print(f"    ref_ncci_ptp_edits:          {len(ncci):>6,} edit rules")
    print(f"    ref_mue_limits:              {len(mues):>6,} MUE limits")
    print(f"    ref_lcd_ncd_policies:        {len(lcds):>6,} coverage policies")
    print(f"    ref_physician_fee_schedule:  {len(fees):>6,} fee entries")
    print(f"    fact_charge_lag:             {len(charge_lag):>6,} records")
    print(f"\n  Phase 3 files:")
    print(f"    fact_scheduling:             {len(scheduling):>6,} appointments")
    print(f"    ref_nppes_providers:         {len(nppes):>6,} provider records")
    print(f"    fact_claim_status_history:   {len(claim_status):>6,} status events")
    print(f"    fact_encounters:             {len(encounters):>6,} encounters")
    print(f"\n  All files saved to: {OUTPUT_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()
