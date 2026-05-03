"""
Claims Denial Intelligence & Prevention Platform — Core Data Generator v2
=========================================================================
Generates 16 synthetic CSV files simulating Meridian Regional Medical Center,
a 312-bed community teaching hospital in Charlotte, NC over 24 months (Jan 2024 - Dec 2025).

Usage:  python generate_core_data_v2.py
Output: ../data/raw_v2/  (16 CSV files)
"""

import csv
import random
import os
from datetime import datetime, timedelta, date
from pathlib import Path
from collections import Counter

random.seed(2024)

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "raw_v2"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# DIMENSION DATA DEFINITIONS
# ============================================================

PAYER_DATA = [
    ("PAY001", "Medicare FFS", "Medicare", 0.22, 0.12, 32, 0.3),
    ("PAY002", "Blue Cross NC", "Commercial", 0.15, 0.16, 28, 0.5),
    ("PAY003", "NC Medicaid", "Medicaid", 0.15, 0.14, 45, 0.4),
    ("PAY004", "UnitedHealthcare MA", "Medicare Advantage", 0.08, 0.22, 25, 0.7),
    ("PAY005", "UnitedHealthcare Commercial", "Commercial", 0.08, 0.19, 24, 0.6),
    ("PAY006", "Aetna", "Commercial", 0.06, 0.17, 26, 0.55),
    ("PAY007", "Humana MA", "Medicare Advantage", 0.05, 0.21, 27, 0.65),
    ("PAY008", "Cigna", "Commercial", 0.05, 0.18, 23, 0.5),
    ("PAY009", "Medicaid MCO - AmeriHealth", "Medicaid MCO", 0.05, 0.15, 40, 0.45),
    ("PAY010", "Self-Pay", "Self-Pay", 0.04, 0.0, 0, 0.0),
    ("PAY011", "Tricare", "Government", 0.04, 0.10, 30, 0.35),
    ("PAY012", "Workers Comp - Sedgwick", "Workers Comp", 0.03, 0.08, 35, 0.25),
]

FACILITIES = [
    ("FAC001", "Meridian Regional Medical Center - Main Campus", "Acute Care Hospital", 312, "4200 Providence Rd, Charlotte, NC 28211"),
    ("FAC002", "Meridian Ambulatory Surgery Center", "ASC", 0, "4250 Providence Rd, Charlotte, NC 28211"),
    ("FAC003", "Meridian Primary Care - University", "Clinic", 0, "9105 University City Blvd, Charlotte, NC 28213"),
    ("FAC004", "Meridian Primary Care - Ballantyne", "Clinic", 0, "15235 John J Delaney Dr, Charlotte, NC 28277"),
    ("FAC005", "Meridian Imaging Center", "Imaging", 0, "4300 Providence Rd, Charlotte, NC 28211"),
    ("FAC006", "Meridian Urgent Care - Northlake", "Urgent Care", 0, "9820 Northlake Centre Pkwy, Charlotte, NC 28216"),
    ("FAC007", "Meridian Rehabilitation Center", "Rehab", 24, "4350 Providence Rd, Charlotte, NC 28211"),
]

DEPARTMENTS = [
    ("DEPT01", "Emergency Medicine", "Emergency", 0.12, 0.05),
    ("DEPT02", "Internal Medicine", "Medicine", 0.14, 0.15),
    ("DEPT03", "Cardiology", "Medicine", 0.10, 0.25),
    ("DEPT04", "Orthopedics", "Surgical", 0.09, 0.35),
    ("DEPT05", "General Surgery", "Surgical", 0.08, 0.20),
    ("DEPT06", "Obstetrics & Gynecology", "Women's Health", 0.07, 0.10),
    ("DEPT07", "Radiology", "Ancillary", 0.08, 0.30),
    ("DEPT08", "Pathology & Lab", "Ancillary", 0.06, 0.02),
    ("DEPT09", "Neurology", "Medicine", 0.05, 0.20),
    ("DEPT10", "Pulmonology", "Medicine", 0.05, 0.15),
    ("DEPT11", "Oncology", "Medicine", 0.05, 0.40),
    ("DEPT12", "Pediatrics", "Pediatrics", 0.04, 0.08),
    ("DEPT13", "Psychiatry", "Behavioral Health", 0.04, 0.12),
    ("DEPT14", "Physical Therapy", "Rehab", 0.03, 0.18),
]

ICD10_CODES = [
    ("I10", "Essential hypertension", "Circulatory", 0.08),
    ("E11.9", "Type 2 diabetes without complications", "Endocrine", 0.06),
    ("J06.9", "Acute upper respiratory infection", "Respiratory", 0.05),
    ("M54.5", "Low back pain", "Musculoskeletal", 0.05),
    ("I25.10", "Atherosclerotic heart disease", "Circulatory", 0.04),
    ("J44.1", "COPD with acute exacerbation", "Respiratory", 0.03),
    ("N39.0", "Urinary tract infection", "Genitourinary", 0.03),
    ("K21.0", "GERD with esophagitis", "Digestive", 0.03),
    ("F32.1", "Major depressive disorder, moderate", "Mental", 0.02),
    ("E78.5", "Hyperlipidemia", "Endocrine", 0.04),
    ("I48.91", "Atrial fibrillation, unspecified", "Circulatory", 0.03),
    ("J18.9", "Pneumonia, unspecified", "Respiratory", 0.02),
    ("M79.3", "Panniculitis, unspecified", "Musculoskeletal", 0.01),
    ("G43.909", "Migraine, unspecified", "Nervous", 0.02),
    ("R10.9", "Unspecified abdominal pain", "Symptoms", 0.02),
    ("K80.20", "Gallstones without obstruction", "Digestive", 0.02),
    ("I50.9", "Heart failure, unspecified", "Circulatory", 0.03),
    ("E11.65", "Type 2 diabetes with hyperglycemia", "Endocrine", 0.02),
    ("J45.20", "Mild intermittent asthma, uncomplicated", "Respiratory", 0.02),
    ("M17.11", "Primary osteoarthritis, right knee", "Musculoskeletal", 0.02),
    ("C50.911", "Malignant neoplasm, right female breast", "Neoplasm", 0.01),
    ("Z87.891", "Personal history of nicotine dependence", "Factors", 0.01),
    ("R07.9", "Chest pain, unspecified", "Symptoms", 0.02),
    ("N18.3", "Chronic kidney disease, stage 3", "Genitourinary", 0.02),
    ("D64.9", "Anemia, unspecified", "Blood", 0.02),
    ("I63.9", "Cerebral infarction, unspecified", "Circulatory", 0.01),
    ("S72.001A", "Fracture of femur, initial encounter", "Injury", 0.01),
    ("K57.30", "Diverticulosis without hemorrhage", "Digestive", 0.01),
    ("G47.33", "Obstructive sleep apnea", "Nervous", 0.02),
    ("M48.06", "Spinal stenosis, lumbar region", "Musculoskeletal", 0.01),
    ("I21.09", "ST elevation MI, anterior wall", "Circulatory", 0.01),
    ("Z96.641", "Presence of right artificial hip joint", "Factors", 0.01),
    ("E03.9", "Hypothyroidism, unspecified", "Endocrine", 0.02),
    ("J96.01", "Acute respiratory failure with hypoxia", "Respiratory", 0.01),
    ("R06.02", "Shortness of breath", "Symptoms", 0.02),
    ("N40.0", "Benign prostatic hyperplasia without LUTS", "Genitourinary", 0.01),
    ("K59.00", "Constipation, unspecified", "Digestive", 0.01),
    ("F41.1", "Generalized anxiety disorder", "Mental", 0.02),
    ("I73.9", "Peripheral vascular disease", "Circulatory", 0.01),
    ("M62.838", "Other muscle spasm", "Musculoskeletal", 0.01),
    ("Z23", "Encounter for immunization", "Factors", 0.01),
    ("B34.9", "Viral infection, unspecified", "Infectious", 0.01),
    ("L03.116", "Cellulitis of left lower limb", "Skin", 0.01),
    ("T81.4XXA", "Infection following procedure", "Injury", 0.005),
    ("S82.001A", "Fracture of tibia, initial", "Injury", 0.005),
    ("O80", "Full-term uncomplicated delivery", "Pregnancy", 0.01),
    ("O99.89", "Other specified diseases complicating pregnancy", "Pregnancy", 0.005),
    ("Z38.00", "Single liveborn infant, born in hospital", "Perinatal", 0.01),
    ("P59.9", "Neonatal jaundice, unspecified", "Perinatal", 0.005),
    ("R50.9", "Fever, unspecified", "Symptoms", 0.01),
    ("Z51.11", "Encounter for chemotherapy", "Factors", 0.01),
    ("C34.90", "Malignant neoplasm of lung", "Neoplasm", 0.005),
    ("G40.909", "Epilepsy, unspecified", "Nervous", 0.005),
    ("I70.0", "Atherosclerosis of aorta", "Circulatory", 0.005),
    ("K35.80", "Acute appendicitis, unspecified", "Digestive", 0.005),
    ("M75.110", "Rotator cuff tear, right shoulder", "Musculoskeletal", 0.005),
    ("S52.501A", "Fracture of radius, initial", "Injury", 0.005),
    ("Z80.3", "Family history of breast cancer", "Factors", 0.005),
    ("E66.01", "Morbid obesity due to excess calories", "Endocrine", 0.01),
    ("I11.9", "Hypertensive heart disease without HF", "Circulatory", 0.005),
    ("J20.9", "Acute bronchitis, unspecified", "Respiratory", 0.01),
    ("M25.561", "Pain in right knee", "Musculoskeletal", 0.01),
    ("R11.2", "Nausea with vomiting", "Symptoms", 0.005),
    ("Z01.818", "Encounter for other preprocedural exam", "Factors", 0.005),
    ("F10.20", "Alcohol dependence, uncomplicated", "Mental", 0.005),
    ("N20.0", "Calculus of kidney", "Genitourinary", 0.005),
    ("I42.9", "Cardiomyopathy, unspecified", "Circulatory", 0.005),
    ("K70.30", "Alcoholic cirrhosis without ascites", "Digestive", 0.005),
    ("G20", "Parkinson's disease", "Nervous", 0.005),
    ("M06.9", "Rheumatoid arthritis, unspecified", "Musculoskeletal", 0.005),
    ("D50.9", "Iron deficiency anemia, unspecified", "Blood", 0.005),
    ("Z95.1", "Presence of aortocoronary bypass graft", "Factors", 0.005),
    ("I26.99", "Other pulmonary embolism", "Circulatory", 0.005),
    ("S06.0X0A", "Concussion without LOC, initial", "Injury", 0.005),
    ("M16.11", "Primary osteoarthritis, right hip", "Musculoskeletal", 0.005),
    ("C61", "Malignant neoplasm of prostate", "Neoplasm", 0.005),
    ("Z12.31", "Encounter for screening mammogram", "Factors", 0.005),
    ("R42", "Dizziness and giddiness", "Symptoms", 0.005),
    ("E87.1", "Hypo-osmolality and hyponatremia", "Endocrine", 0.005),
    ("A41.9", "Sepsis, unspecified organism", "Infectious", 0.005),
]

CPT_CODES = [
    ("99213", "Office visit, established, low", "E&M", 95.00, "DEPT02"),
    ("99214", "Office visit, established, moderate", "E&M", 150.00, "DEPT02"),
    ("99215", "Office visit, established, high", "E&M", 210.00, "DEPT02"),
    ("99203", "Office visit, new, low", "E&M", 130.00, "DEPT02"),
    ("99204", "Office visit, new, moderate", "E&M", 200.00, "DEPT02"),
    ("99232", "Subsequent hospital care, moderate", "E&M", 120.00, "DEPT02"),
    ("99233", "Subsequent hospital care, high", "E&M", 175.00, "DEPT02"),
    ("99223", "Initial hospital care, high", "E&M", 280.00, "DEPT02"),
    ("99285", "ED visit, high complexity", "E&M", 450.00, "DEPT01"),
    ("99283", "ED visit, moderate complexity", "E&M", 250.00, "DEPT01"),
    ("99284", "ED visit, moderately high", "E&M", 350.00, "DEPT01"),
    ("99291", "Critical care, first 30-74 min", "E&M", 550.00, "DEPT01"),
    ("36415", "Venipuncture", "Lab", 12.00, "DEPT08"),
    ("80053", "Comprehensive metabolic panel", "Lab", 45.00, "DEPT08"),
    ("85025", "Complete blood count", "Lab", 30.00, "DEPT08"),
    ("80061", "Lipid panel", "Lab", 50.00, "DEPT08"),
    ("81001", "Urinalysis, automated", "Lab", 15.00, "DEPT08"),
    ("71046", "Chest X-ray, 2 views", "Radiology", 85.00, "DEPT07"),
    ("74177", "CT abdomen/pelvis with contrast", "Radiology", 650.00, "DEPT07"),
    ("70553", "MRI brain with/without contrast", "Radiology", 1200.00, "DEPT07"),
    ("77067", "Screening mammography, bilateral", "Radiology", 180.00, "DEPT07"),
    ("72148", "MRI lumbar spine without contrast", "Radiology", 900.00, "DEPT07"),
    ("93000", "Electrocardiogram, 12-lead", "Cardiology", 55.00, "DEPT03"),
    ("93306", "Echocardiography, complete", "Cardiology", 450.00, "DEPT03"),
    ("93458", "Left heart catheterization", "Cardiology", 2800.00, "DEPT03"),
    ("93010", "ECG interpretation only", "Cardiology", 25.00, "DEPT03"),
    ("93880", "Duplex scan of carotid arteries", "Cardiology", 350.00, "DEPT03"),
    ("27447", "Total knee arthroplasty", "Orthopedics", 8500.00, "DEPT04"),
    ("27130", "Total hip arthroplasty", "Orthopedics", 9200.00, "DEPT04"),
    ("29881", "Knee arthroscopy/meniscectomy", "Orthopedics", 3500.00, "DEPT04"),
    ("23472", "Shoulder arthroplasty", "Orthopedics", 8800.00, "DEPT04"),
    ("27236", "Open treatment femoral fracture", "Orthopedics", 7500.00, "DEPT04"),
    ("47562", "Laparoscopic cholecystectomy", "Surgery", 4200.00, "DEPT05"),
    ("44970", "Laparoscopic appendectomy", "Surgery", 3800.00, "DEPT05"),
    ("49505", "Inguinal hernia repair", "Surgery", 3200.00, "DEPT05"),
    ("43239", "Upper GI endoscopy with biopsy", "Surgery", 1800.00, "DEPT05"),
    ("45380", "Colonoscopy with biopsy", "Surgery", 2100.00, "DEPT05"),
    ("59400", "Routine obstetric care, vaginal", "OB/GYN", 5500.00, "DEPT06"),
    ("59510", "Routine obstetric care, cesarean", "OB/GYN", 7200.00, "DEPT06"),
    ("58661", "Laparoscopic removal of adnexa", "OB/GYN", 4500.00, "DEPT06"),
    ("59025", "Fetal non-stress test", "OB/GYN", 120.00, "DEPT06"),
    ("96413", "Chemotherapy infusion, first hour", "Oncology", 450.00, "DEPT11"),
    ("96415", "Chemotherapy infusion, additional hour", "Oncology", 250.00, "DEPT11"),
    ("77385", "IMRT delivery, simple", "Oncology", 800.00, "DEPT11"),
    ("77386", "IMRT delivery, complex", "Oncology", 1200.00, "DEPT11"),
    ("90837", "Psychotherapy, 60 minutes", "Behavioral", 175.00, "DEPT13"),
    ("90834", "Psychotherapy, 45 minutes", "Behavioral", 130.00, "DEPT13"),
    ("90847", "Family psychotherapy with patient", "Behavioral", 150.00, "DEPT13"),
    ("97110", "Therapeutic exercises", "Rehab", 65.00, "DEPT14"),
    ("97140", "Manual therapy techniques", "Rehab", 70.00, "DEPT14"),
    ("97530", "Therapeutic activities", "Rehab", 60.00, "DEPT14"),
    ("95819", "EEG with sleep", "Neurology", 350.00, "DEPT09"),
    ("95907", "Nerve conduction study, 1-2", "Neurology", 250.00, "DEPT09"),
    ("94010", "Spirometry", "Pulmonology", 85.00, "DEPT10"),
    ("94060", "Bronchospasm evaluation", "Pulmonology", 120.00, "DEPT10"),
    ("31622", "Diagnostic bronchoscopy", "Pulmonology", 1500.00, "DEPT10"),
    ("90471", "Immunization admin, first", "Preventive", 25.00, "DEPT12"),
    ("99381", "Preventive visit, infant", "Preventive", 180.00, "DEPT12"),
    ("99391", "Preventive visit, child", "Preventive", 160.00, "DEPT12"),
    ("99395", "Preventive visit, 18-39", "Preventive", 190.00, "DEPT12"),
    ("99396", "Preventive visit, 40-64", "Preventive", 200.00, "DEPT12"),
]

SPECIALTIES = [
    ("Internal Medicine", "DEPT02", 12),
    ("Emergency Medicine", "DEPT01", 10),
    ("Cardiology", "DEPT03", 8),
    ("Orthopedic Surgery", "DEPT04", 7),
    ("General Surgery", "DEPT05", 6),
    ("OB/GYN", "DEPT06", 6),
    ("Radiology", "DEPT07", 6),
    ("Pathology", "DEPT08", 4),
    ("Neurology", "DEPT09", 5),
    ("Pulmonology", "DEPT10", 4),
    ("Oncology", "DEPT11", 5),
    ("Pediatrics", "DEPT12", 5),
    ("Psychiatry", "DEPT13", 4),
    ("Physical Medicine", "DEPT14", 3),
]

FIRST_NAMES = ["James","Mary","Robert","Patricia","John","Jennifer","Michael","Linda","David","Elizabeth",
    "William","Barbara","Richard","Susan","Joseph","Jessica","Thomas","Sarah","Charles","Karen",
    "Daniel","Lisa","Matthew","Betty","Anthony","Sandra","Mark","Ashley","Donald","Dorothy",
    "Steven","Kimberly","Paul","Emily","Andrew","Donna","Joshua","Michelle","Kenneth","Carol"]
LAST_NAMES = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez","Martinez",
    "Hernandez","Lopez","Gonzalez","Wilson","Anderson","Thomas","Taylor","Moore","Jackson","Martin",
    "Lee","Perez","Thompson","White","Harris","Sanchez","Clark","Ramirez","Lewis","Robinson"]

CARC_CODES = [
    ("1", "Deductible", "PR"),("2", "Coinsurance", "PR"),("3", "Copay", "PR"),
    ("4", "Procedure not covered by plan", "CO"),("5", "Services not authorized", "CO"),
    ("16", "Claim lacks required information", "CO"),("18", "Duplicate claim/service", "CO"),
    ("22", "Required effective date coordination of benefits", "CO"),
    ("27", "Expenses incurred after coverage terminated", "CO"),
    ("29", "Time limit for filing has expired", "CO"),
    ("31", "Patient cannot be identified as our insured", "CO"),
    ("45", "Charges exceed fee schedule/usual & customary", "CO"),
    ("50", "Non-covered service - not deemed medical necessity", "CO"),
    ("55", "Procedure requires PA; not obtained", "CO"),
    ("96", "Non-covered charges", "CO"),("97", "Payment adjusted - benefit maximum reached", "CO"),
    ("109", "Claim not covered by this payer", "CO"),
    ("119", "Benefit maximum for this time period reached", "CO"),
    ("125", "Payment adjusted - submission/billing error", "CO"),
    ("136", "Claim not covered; patient ineligible", "CO"),
    ("151", "Payment adjusted - prior payer paid above allowed", "OA"),
    ("167", "Diagnosis not consistent with procedure", "CO"),
    ("170", "Payment made to patient; provider not enrolled", "CO"),
    ("181", "Procedure code inconsistent with modifier", "CO"),
    ("182", "Procedure code inconsistent with diagnosis", "CO"),
    ("197", "Precertification/authorization absent", "CO"),
    ("204", "Service not covered unless condition met", "CO"),
    ("219", "Claim denied based on payer processing guidelines", "CO"),
    ("226", "Information requested not furnished; claim denied", "CO"),
    ("242", "Services not provided by network providers", "CO"),
    ("252", "Service not adjudicated; requires medical records", "CO"),
]

RARC_CODES = [
    ("N1", "Alert: You may appeal this decision"),
    ("N4", "Alert: Missing/Incomplete/Invalid procedure code"),
    ("N30", "Alert: Missing/Incomplete patient information"),
    ("N56", "Alert: Procedure code billed is not correct"),
    ("N115", "Alert: This decision was based on a National Coverage Determination"),
    ("N386", "Alert: This decision was based on a Local Coverage Determination"),
    ("M15", "Alert: Separately billed services not allowed"),
    ("M79", "Alert: Procedure requires documentation to support medical necessity"),
    ("MA04", "Alert: Secondary payment cannot be determined"),
    ("MA130", "Alert: Claim was denied based on clinical review"),
    ("N362", "Alert: Missing/Incomplete authorization number"),
    ("N657", "Alert: Provider not enrolled; cannot adjudicate"),
]

# Root cause categories with target distributions and associated workflow failures
ROOT_CAUSES = [
    ("Prior Authorization", 0.31, "prior_authorization"),
    ("Missing/Inaccurate Data", 0.24, "patient_registration"),
    ("Eligibility", 0.20, "eligibility_verification"),
    ("Coding Errors", 0.18, "medical_coding"),
    ("Medical Necessity", 0.05, "clinical_service"),
    ("Duplicate", 0.02, "claim_scrubbing"),
]
# Timely Filing ~1% handled separately

WORKFLOW_STEPS = [
    "patient_registration",
    "eligibility_verification",
    "prior_authorization",
    "clinical_service",
    "medical_coding",
    "charge_capture",
    "claim_scrubbing",
    "claim_submission",
]

# Seasonal multipliers by month (1=Jan..12=Dec)
SEASONAL = {1:1.12, 2:1.08, 3:1.05, 4:1.02, 5:0.98, 6:0.94,
            7:0.92, 8:0.93, 9:0.97, 10:1.01, 11:1.00, 12:0.98}

def write_csv(filename, headers, rows):
    path = OUTPUT_DIR / filename
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    return len(rows)

# ============================================================
# GENERATE DIMENSIONS
# ============================================================

def gen_dim_payers():
    rows = []
    for pid, name, ptype, share, denial_rate, days_to_pay, pa_strict in PAYER_DATA:
        rows.append([pid, name, ptype, share, denial_rate, days_to_pay, pa_strict,
                     f"POL-{pid[-3:]}", "Active"])
    return write_csv("dim_payers.csv",
        ["payer_id","payer_name","payer_type","market_share","denial_rate",
         "avg_days_to_pay","pa_strictness","policy_prefix","status"], rows)

def gen_dim_facilities():
    rows = []
    for fid, name, ftype, beds, addr in FACILITIES:
        rows.append([fid, name, ftype, beds, addr, "Active", "1234567890"])
    return write_csv("dim_facilities.csv",
        ["facility_id","facility_name","facility_type","bed_count","address","status","tax_id"], rows)

def gen_dim_departments():
    rows = []
    for did, name, sline, share, pa_freq in DEPARTMENTS:
        rows.append([did, name, sline, share, pa_freq, random.randint(8, 25)])
    return write_csv("dim_departments.csv",
        ["department_id","department_name","service_line","claim_share","pa_frequency","avg_daily_volume"], rows)

def gen_dim_icd10():
    rows = []
    for code, desc, system, freq in ICD10_CODES:
        rows.append([code, desc, system, freq, random.choice(["Acute","Chronic","Both"])])
    return write_csv("dim_icd10_codes.csv",
        ["icd10_code","description","body_system","relative_frequency","acuity_type"], rows)

def gen_dim_cpt():
    rows = []
    for code, desc, cat, charge, dept in CPT_CODES:
        rows.append([code, desc, cat, charge, dept, random.choice(["Professional","Facility","Both"])])
    return write_csv("dim_cpt_codes.csv",
        ["cpt_code","description","category","standard_charge","primary_department","billing_type"], rows)

def gen_dim_providers():
    rows = []
    pid = 1
    for spec, dept, count in SPECIALTIES:
        for _ in range(count):
            fn = random.choice(FIRST_NAMES)
            ln = random.choice(LAST_NAMES)
            npi = f"1{random.randint(100000000,999999999)}"
            coding_acc = round(random.uniform(0.78, 0.99), 3)
            doc_comp = round(random.uniform(0.75, 0.98), 3)
            years = random.randint(2, 30)
            rows.append([f"PROV{pid:03d}", f"Dr. {fn} {ln}", npi, spec, dept,
                         coding_acc, doc_comp, years, "Active",
                         random.choice(["MD","DO"])])
            pid += 1
    return write_csv("dim_providers.csv",
        ["provider_id","provider_name","npi","specialty","department_id",
         "coding_accuracy_score","documentation_completeness_score",
         "years_experience","status","credential"], rows)

def gen_dim_patients():
    rows = []
    payer_weights = [p[3] for p in PAYER_DATA]
    payer_ids = [p[0] for p in PAYER_DATA]
    for i in range(15000):
        fn = random.choice(FIRST_NAMES)
        ln = random.choice(LAST_NAMES)
        age = random.randint(0, 95)
        gender = random.choice(["M","F"])
        # Age-based payer assignment
        if age >= 65:
            payer = random.choice(["PAY001","PAY004","PAY007"])  # Medicare payers
        elif age < 18:
            payer = random.choices(["PAY002","PAY003","PAY005","PAY009","PAY012","PAY010"],
                                   weights=[0.3,0.3,0.15,0.15,0.05,0.05])[0]
        else:
            payer = random.choices(payer_ids, weights=payer_weights)[0]
        risk_score = round(random.uniform(0.1, 4.5) if age > 50 else random.uniform(0.1, 2.5), 2)
        zip_code = f"28{random.randint(200,299)}"
        rows.append([f"PAT{i+1:06d}", fn, ln, age, gender, payer, risk_score,
                     zip_code, random.choice(["English","Spanish","Vietnamese","Other"]),
                     "Active"])
    return write_csv("dim_patients.csv",
        ["patient_id","first_name","last_name","age","gender","primary_payer_id",
         "risk_score","zip_code","language","status"], rows)

def gen_dim_payer_contracts():
    categories = list(set(c[2] for c in CPT_CODES))
    rows = []
    cid = 1
    for pid, pname, ptype, *_ in PAYER_DATA:
        if pid == "PAY010":  # Self-pay no contracts
            continue
        for cat in categories:
            if ptype == "Medicare":
                reimb_pct = round(random.uniform(0.75, 0.85), 3)
            elif ptype == "Medicare Advantage":
                reimb_pct = round(random.uniform(0.80, 0.92), 3)
            elif ptype == "Commercial":
                reimb_pct = round(random.uniform(0.85, 1.20), 3)
            elif ptype in ("Medicaid", "Medicaid MCO"):
                reimb_pct = round(random.uniform(0.55, 0.70), 3)
            else:
                reimb_pct = round(random.uniform(0.70, 0.90), 3)
            rows.append([f"CON{cid:04d}", pid, cat, reimb_pct,
                         "2024-01-01", "2025-12-31", "Active"])
            cid += 1
    return write_csv("dim_payer_contracts.csv",
        ["contract_id","payer_id","cpt_category","reimbursement_pct_of_charge",
         "effective_date","end_date","status"], rows)

def gen_ref_carc():
    rows = [[c, d, g] for c, d, g in CARC_CODES]
    return write_csv("ref_carc_codes.csv", ["carc_code","description","group_code"], rows)

def gen_ref_rarc():
    rows = [[c, d] for c, d in RARC_CODES]
    return write_csv("ref_rarc_codes.csv", ["rarc_code","description"], rows)

# ============================================================
# GENERATE FACTS
# ============================================================

def generate_all_facts(providers, patients, payer_lookup):
    """Generate all fact tables in a single pass for efficiency."""

    # Pre-compute lookup structures
    provider_list = providers  # list of tuples from dim generation
    payer_ids_no_self = [p[0] for p in PAYER_DATA if p[0] != "PAY010"]
    dept_list = [d[0] for d in DEPARTMENTS]
    dept_weights = [d[3] for d in DEPARTMENTS]
    cpt_by_dept = {}
    for code, desc, cat, charge, dept in CPT_CODES:
        cpt_by_dept.setdefault(dept, []).append((code, charge, cat))
    # Fallback CPTs
    all_cpts = [(code, charge, cat) for code, desc, cat, charge, dept in CPT_CODES]

    icd_codes = [c[0] for c in ICD10_CODES]
    icd_weights = [c[3] for c in ICD10_CODES]

    # CARC mapping by root cause
    carc_by_cause = {
        "Prior Authorization": ["5","55","197"],
        "Missing/Inaccurate Data": ["16","226","252"],
        "Eligibility": ["27","31","136","109"],
        "Coding Errors": ["125","167","181","182"],
        "Medical Necessity": ["50","204","96"],
        "Duplicate": ["18"],
        "Timely Filing": ["29"],
    }
    rarc_by_cause = {
        "Prior Authorization": ["N362","MA130"],
        "Missing/Inaccurate Data": ["N30","N4"],
        "Eligibility": ["MA04","N657"],
        "Coding Errors": ["N56","M15"],
        "Medical Necessity": ["M79","N115","N386"],
        "Duplicate": ["M15"],
        "Timely Filing": ["N1"],
    }

    # Workflow failure issues
    workflow_issues = {
        "patient_registration": ["Missing demographics","Invalid address","Missing insurance ID",
                                  "Name mismatch","DOB incorrect","Missing subscriber info"],
        "eligibility_verification": ["Coverage terminated","Plan not active","Patient not found",
                                      "Benefits exhausted","COB issue","Wrong member ID"],
        "prior_authorization": ["PA not obtained","PA expired","Wrong procedure on PA",
                                 "PA denied by payer","Retro auth required","Auth number invalid"],
        "clinical_service": ["Documentation insufficient","Medical necessity not established",
                             "Missing clinical notes","Incomplete H&P","Missing orders"],
        "medical_coding": ["Incorrect CPT selected","Modifier missing","DX not supporting CPT",
                           "Unbundling error","Upcoding detected","Sequencing error"],
        "charge_capture": ["Charge not posted","Duplicate charge","Wrong quantity",
                           "Missing revenue code","Late charge entry"],
        "claim_scrubbing": ["Duplicate claim detected","NCCI edit violation","MUE exceeded",
                            "Invalid place of service","Missing referring provider"],
        "claim_submission": ["Payer rejection - format","Wrong payer ID","Timely filing risk",
                             "Missing attachment","EDI envelope error"],
    }

    # Open all output files
    claims_file = open(OUTPUT_DIR / "fact_claims.csv", 'w', newline='')
    lines_file = open(OUTPUT_DIR / "fact_claim_lines.csv", 'w', newline='')
    remit_file = open(OUTPUT_DIR / "fact_remittance.csv", 'w', newline='')
    denial_file = open(OUTPUT_DIR / "fact_denials.csv", 'w', newline='')
    appeal_file = open(OUTPUT_DIR / "fact_appeals.csv", 'w', newline='')
    wf_file = open(OUTPUT_DIR / "fact_workflow_events.csv", 'w', newline='')

    cw = csv.writer(claims_file)
    lw = csv.writer(lines_file)
    rw = csv.writer(remit_file)
    dw = csv.writer(denial_file)
    aw = csv.writer(appeal_file)
    ww = csv.writer(wf_file)

    cw.writerow(["claim_id","patient_id","provider_id","payer_id","facility_id","department_id",
                 "service_date","submission_date","total_charge","total_allowed","total_paid",
                 "patient_responsibility","status","claim_type","place_of_service",
                 "primary_icd10","days_in_ar","is_clean_claim","pa_required","pa_obtained",
                 "pa_number"])
    lw.writerow(["line_id","claim_id","line_number","cpt_code","cpt_category","modifier",
                 "units","charge_amount","allowed_amount","paid_amount","icd10_pointer"])
    rw.writerow(["remittance_id","claim_id","payer_id","check_date","check_number",
                 "total_charge","total_allowed","total_paid","adjustment_amount",
                 "adjudication_status","carc_code","rarc_code"])
    dw.writerow(["denial_id","claim_id","payer_id","denial_date","root_cause_category",
                 "carc_code","rarc_code","denial_amount","workflow_failure_point",
                 "is_preventable","denial_reason_text","days_to_denial"])
    aw.writerow(["appeal_id","denial_id","claim_id","appeal_date","appeal_level",
                 "appeal_reason","outcome","overturn_amount","days_to_resolution","submitted_by"])
    ww.writerow(["event_id","claim_id","workflow_step","step_order","event_timestamp",
                 "status","issues_flagged","performed_by","duration_minutes"])

    # Counters
    claim_count = 0
    line_count = 0
    remit_count = 0
    denial_count = 0
    appeal_count = 0
    wf_count = 0

    # Generate claims month by month
    start_date = date(2024, 1, 1)

    for year in (2024, 2025):
        for month in range(1, 13):
            base_claims = 5000
            multiplier = SEASONAL[month]
            month_claims = int(base_claims * multiplier)

            # Days in this month
            if month == 12:
                days_in_month = 31
            else:
                next_m = date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)
                days_in_month = (next_m - date(year, month, 1)).days

            for _ in range(month_claims):
                claim_count += 1
                claim_id = f"CLM{claim_count:07d}"

                # Pick patient
                pat_idx = random.randint(0, 14999)
                pat_id = f"PAT{pat_idx+1:06d}"
                pat_payer = patients[pat_idx]  # payer_id stored

                # Pick provider
                prov_idx = random.randint(0, len(provider_list) - 1)
                prov = provider_list[prov_idx]
                prov_id = prov[0]
                prov_dept = prov[1]
                prov_coding_acc = prov[2]

                payer_id = pat_payer
                is_self_pay = (payer_id == "PAY010")

                # Department & facility
                dept_id = prov_dept
                fac_id = random.choices(["FAC001","FAC002","FAC003","FAC004","FAC005","FAC006","FAC007"],
                                        weights=[0.45, 0.12, 0.12, 0.10, 0.08, 0.08, 0.05])[0]

                # Service date
                day = random.randint(1, days_in_month)
                svc_date = date(year, month, day)
                # Submission 1-5 days after service
                sub_lag = random.randint(1, 5)
                sub_date = svc_date + timedelta(days=sub_lag)

                # Primary ICD10
                primary_icd = random.choices(icd_codes, weights=icd_weights)[0]

                # PA required?
                dept_pa_freq = 0.15
                for d in DEPARTMENTS:
                    if d[0] == dept_id:
                        dept_pa_freq = d[4]
                        break
                pa_required = random.random() < dept_pa_freq
                pa_obtained = pa_required and (random.random() < 0.82)
                pa_number = f"PA{random.randint(100000,999999)}" if pa_obtained else ""

                # Claim lines (1-5 procedures per claim, avg ~2.5)
                num_lines = random.choices([1,2,3,4,5], weights=[0.20,0.35,0.25,0.12,0.08])[0]
                dept_cpts = cpt_by_dept.get(dept_id, all_cpts[:10])

                total_charge = 0.0
                claim_lines = []
                for ln in range(1, num_lines + 1):
                    line_count += 1
                    cpt_info = random.choice(dept_cpts)
                    cpt_code, charge, cpt_cat = cpt_info
                    units = 1 if charge > 200 else random.randint(1, 3)
                    line_charge = charge * units
                    modifier = random.choice(["","","","25","59","76","LT","RT"])
                    total_charge += line_charge
                    claim_lines.append((f"LN{line_count:08d}", claim_id, ln, cpt_code, cpt_cat,
                                       modifier, units, line_charge, primary_icd))

                # ---- WORKFLOW SIMULATION ----
                # Each step can pass or fail; failures drive denials
                wf_failures = {}  # step -> issue
                wf_events = []
                event_time = datetime(year, month, day, 8, 0) + timedelta(minutes=random.randint(0, 480))

                for step_order, step in enumerate(WORKFLOW_STEPS, 1):
                    wf_count += 1
                    # Failure probability per step (tuned for ~18% overall denial rate)
                    if step == "patient_registration":
                        fail_prob = 0.055
                    elif step == "eligibility_verification":
                        fail_prob = 0.048
                    elif step == "prior_authorization":
                        fail_prob = 0.08 if pa_required else 0.007
                        if pa_required and not pa_obtained:
                            fail_prob = 0.90
                    elif step == "clinical_service":
                        fail_prob = 0.02
                    elif step == "medical_coding":
                        fail_prob = max(0.035, 1.0 - prov_coding_acc)
                    elif step == "charge_capture":
                        fail_prob = 0.022
                    elif step == "claim_scrubbing":
                        fail_prob = 0.018
                    else:  # claim_submission
                        fail_prob = 0.012

                    step_failed = random.random() < fail_prob
                    status = "fail" if step_failed else "pass"
                    issue = ""
                    if step_failed:
                        issue = random.choice(workflow_issues[step])
                        wf_failures[step] = issue

                    duration = random.randint(2, 45)
                    performer = prov_id if step in ("clinical_service","medical_coding") else "SYSTEM"
                    wf_events.append((f"WF{wf_count:08d}", claim_id, step, step_order,
                                     event_time.strftime("%Y-%m-%d %H:%M:%S"), status, issue,
                                     performer, duration))
                    event_time += timedelta(minutes=duration + random.randint(5, 60))

                # Write workflow events
                ww.writerows(wf_events)

                # ---- DENIAL DETERMINATION ----
                # Denials driven by workflow failures
                denied = False
                root_cause = ""
                failure_point = ""

                if not is_self_pay and wf_failures:
                    # Map workflow failures to denial probability
                    # More failures = higher denial probability
                    denial_prob = 0.0
                    primary_failure = None

                    for step, issue in wf_failures.items():
                        if step == "prior_authorization":
                            denial_prob += 0.75
                            primary_failure = ("Prior Authorization", step)
                        elif step == "eligibility_verification":
                            denial_prob += 0.65
                            primary_failure = primary_failure or ("Eligibility", step)
                        elif step == "medical_coding":
                            denial_prob += 0.55
                            primary_failure = primary_failure or ("Coding Errors", step)
                        elif step == "patient_registration":
                            denial_prob += 0.50
                            primary_failure = primary_failure or ("Missing/Inaccurate Data", step)
                        elif step == "clinical_service":
                            denial_prob += 0.45
                            primary_failure = primary_failure or ("Medical Necessity", step)
                        elif step == "claim_scrubbing":
                            denial_prob += 0.40
                            primary_failure = primary_failure or ("Duplicate", step)
                        elif step == "claim_submission":
                            denial_prob += 0.25
                            primary_failure = primary_failure or ("Timely Filing", step)
                        else:
                            denial_prob += 0.15

                    # Payer denial rate influence
                    payer_denial_rate = payer_lookup.get(payer_id, 0.15)
                    denial_prob = min(0.95, denial_prob * (0.8 + payer_denial_rate))

                    if random.random() < denial_prob and primary_failure:
                        denied = True
                        root_cause = primary_failure[0]
                        failure_point = primary_failure[1]

                elif not is_self_pay and not wf_failures:
                    # Small chance of denial even without workflow failure (payer-side)
                    if random.random() < 0.03:
                        denied = True
                        rc_choice = random.choices(ROOT_CAUSES, weights=[r[1] for r in ROOT_CAUSES])[0]
                        root_cause = rc_choice[0]
                        failure_point = rc_choice[2]

                # ---- FINANCIAL CALCULATIONS ----
                # Reimbursement
                if is_self_pay:
                    total_allowed = total_charge
                    total_paid = total_charge * random.uniform(0.3, 0.7)
                    pat_resp = total_charge - total_paid
                    status_val = "Paid"
                    days_ar = random.randint(0, 90)
                elif denied:
                    total_allowed = 0.0
                    total_paid = 0.0
                    pat_resp = 0.0
                    status_val = "Denied"
                    days_ar = random.randint(15, 60)
                else:
                    # Normal payment
                    reimb_pct = random.uniform(0.60, 1.05)
                    total_allowed = round(total_charge * reimb_pct, 2)
                    copay = random.choice([0, 20, 30, 40, 50, 75])
                    coins = random.uniform(0, 0.20)
                    pat_resp = round(copay + total_allowed * coins * 0.3, 2)
                    total_paid = round(max(0, total_allowed - pat_resp), 2)
                    status_val = "Paid"
                    days_ar = int(random.gauss(29, 12))
                    days_ar = max(5, min(120, days_ar))

                total_charge = round(total_charge, 2)
                is_clean = 1 if not wf_failures and not denied else 0
                claim_type = random.choices(["Professional","Institutional"],
                                           weights=[0.65, 0.35])[0]
                pos = "11" if fac_id in ("FAC003","FAC004") else \
                      "22" if fac_id == "FAC002" else \
                      "23" if fac_id == "FAC001" else "11"

                # Write claim
                cw.writerow([claim_id, pat_id, prov_id, payer_id, fac_id, dept_id,
                            svc_date.isoformat(), sub_date.isoformat(),
                            total_charge, round(total_allowed,2), round(total_paid,2),
                            round(pat_resp,2), status_val, claim_type, pos,
                            primary_icd, days_ar, is_clean,
                            1 if pa_required else 0, 1 if pa_obtained else 0, pa_number])

                # Write claim lines
                for ln_data in claim_lines:
                    lid, cid, lnum, cpt, ccat, mod, units, lcharge, icd_ptr = ln_data
                    if denied:
                        lallowed = 0.0
                        lpaid = 0.0
                    elif is_self_pay:
                        lallowed = lcharge
                        lpaid = round(lcharge * (total_paid / total_charge) if total_charge > 0 else 0, 2)
                    else:
                        lallowed = round(lcharge * (total_allowed / total_charge) if total_charge > 0 else 0, 2)
                        lpaid = round(lcharge * (total_paid / total_charge) if total_charge > 0 else 0, 2)
                    lw.writerow([lid, cid, lnum, cpt, ccat, mod, units,
                                round(lcharge,2), round(lallowed,2), round(lpaid,2), icd_ptr])

                # Write remittance
                remit_count += 1
                adj_status = "Denied" if denied else "Paid"
                adj_amount = round(total_charge - total_paid - pat_resp, 2) if not denied else round(total_charge, 2)
                carc = ""
                rarc = ""
                if denied:
                    carc_list = carc_by_cause.get(root_cause, ["16"])
                    rarc_list = rarc_by_cause.get(root_cause, ["N1"])
                    carc = random.choice(carc_list)
                    rarc = random.choice(rarc_list)
                check_date = (sub_date + timedelta(days=days_ar)).isoformat() if not is_self_pay else ""
                check_num = f"CHK{remit_count:07d}" if not denied and not is_self_pay else ""
                rw.writerow([f"REM{remit_count:07d}", claim_id, payer_id,
                            check_date, check_num, total_charge,
                            round(total_allowed,2), round(total_paid,2),
                            round(adj_amount,2), adj_status, carc, rarc])

                # Write denial
                if denied:
                    denial_count += 1
                    days_to_denial = random.randint(7, 45)
                    denial_date = (sub_date + timedelta(days=days_to_denial)).isoformat()
                    is_preventable = 1 if root_cause in ("Prior Authorization","Missing/Inaccurate Data",
                                                          "Coding Errors","Eligibility") else 0
                    carc_d = random.choice(carc_by_cause.get(root_cause, ["16"]))
                    rarc_d = random.choice(rarc_by_cause.get(root_cause, ["N1"]))
                    reason_text = f"{root_cause}: {wf_failures.get(failure_point, 'Payer determination')}"
                    dw.writerow([f"DEN{denial_count:07d}", claim_id, payer_id,
                                denial_date, root_cause, carc_d, rarc_d,
                                total_charge, failure_point, is_preventable,
                                reason_text, days_to_denial])

                    # Appeal? ~32% of denials
                    if random.random() < 0.32:
                        appeal_count += 1
                        appeal_date = (sub_date + timedelta(days=days_to_denial + random.randint(3, 20))).isoformat()
                        overturn = random.random() < 0.42
                        outcome = "Overturned" if overturn else "Upheld"
                        overturn_amt = round(total_charge * random.uniform(0.6, 1.0), 2) if overturn else 0.0
                        days_to_res = random.randint(14, 90)
                        aw.writerow([f"APL{appeal_count:07d}", f"DEN{denial_count:07d}",
                                    claim_id, appeal_date, random.choice(["First Level","Second Level","External"]),
                                    f"Appeal for {root_cause}", outcome, overturn_amt,
                                    days_to_res, random.choice(provider_list)[0]])

    # Close files
    claims_file.close()
    lines_file.close()
    remit_file.close()
    denial_file.close()
    appeal_file.close()
    wf_file.close()

    return claim_count, line_count, remit_count, denial_count, appeal_count, wf_count


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("Claims Denial Intelligence - Core Data Generator v2")
    print("Meridian Regional Medical Center, Charlotte, NC")
    print("Period: Jan 2024 - Dec 2025 (24 months)")
    print("=" * 60)
    print()

    # Generate dimensions
    print("Generating dimension tables...")
    n = gen_dim_payers()
    print(f"  dim_payers.csv: {n} rows")

    n = gen_dim_facilities()
    print(f"  dim_facilities.csv: {n} rows")

    n = gen_dim_departments()
    print(f"  dim_departments.csv: {n} rows")

    n = gen_dim_icd10()
    print(f"  dim_icd10_codes.csv: {n} rows")

    n = gen_dim_cpt()
    print(f"  dim_cpt_codes.csv: {n} rows")

    n = gen_dim_providers()
    print(f"  dim_providers.csv: {n} rows")

    n = gen_dim_patients()
    print(f"  dim_patients.csv: {n} rows")

    n = gen_dim_payer_contracts()
    print(f"  dim_payer_contracts.csv: {n} rows")

    # Reference tables
    print("\nGenerating reference tables...")
    n = gen_ref_carc()
    print(f"  ref_carc_codes.csv: {n} rows")
    n = gen_ref_rarc()
    print(f"  ref_rarc_codes.csv: {n} rows")

    # Load back patient payers for fact generation
    print("\nLoading patient payer assignments...")
    patients_payers = []
    with open(OUTPUT_DIR / "dim_patients.csv", 'r') as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            patients_payers.append(row[5])  # primary_payer_id

    # Load provider info
    providers_info = []
    with open(OUTPUT_DIR / "dim_providers.csv", 'r') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            providers_info.append((row[0], row[4], float(row[5])))  # id, dept, coding_acc

    # Payer denial rate lookup
    payer_lookup = {p[0]: p[4] for p in PAYER_DATA}

    # Generate facts
    print("\nGenerating fact tables (this may take a moment)...")
    claims, lines, remits, denials, appeals, wf_events = generate_all_facts(
        providers_info, patients_payers, payer_lookup)

    print(f"  fact_claims.csv: {claims:,} rows")
    print(f"  fact_claim_lines.csv: {lines:,} rows")
    print(f"  fact_remittance.csv: {remits:,} rows")
    print(f"  fact_denials.csv: {denials:,} rows")
    print(f"  fact_appeals.csv: {appeals:,} rows")
    print(f"  fact_workflow_events.csv: {wf_events:,} rows")

    # Summary statistics
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    denial_rate = denials / claims * 100
    appeal_rate = appeals / denials * 100 if denials > 0 else 0
    print(f"  Total claims: {claims:,}")
    print(f"  Total denials: {denials:,} ({denial_rate:.1f}%)")
    print(f"  Total appeals: {appeals:,} ({appeal_rate:.1f}% of denials)")
    print(f"  Total claim lines: {lines:,} (avg {lines/claims:.1f} per claim)")
    print(f"  Total workflow events: {wf_events:,} ({wf_events//claims} per claim)")
    print(f"  Output directory: {OUTPUT_DIR}")
    print(f"\n  Files generated: 16")
    print("=" * 60)


if __name__ == "__main__":
    main()
