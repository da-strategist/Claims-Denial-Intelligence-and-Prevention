# Sample claim upload files

For trying **New Claim → Upload claims** against the Meridian organisation. Every patient,
provider, payer and code is from the synthetic Meridian data (`Data/raw_data`), so the files
read as they are. No real patients. Each file has its own claims and patients, so
the files can be uploaded side by side.

| File | What it shows |
|---|---|
| `claims_upload_sample.csv` | 8 claims (15 service lines) across 7 payers. All 8 save as drafts: 6 pass, S05 gets a warning (RULE-007 UnitedHealthcare Coding Compliance) and S08 an error (RULE-002 Missing Prior Authorization: an MRI with `pa_required` but no authorization number). |
| `claims_upload_sample.xlsx` | 8 other claims (17 service lines) as an Excel file, across cardiology, orthopaedics, emergency, behavioural health and surgery. 6 pass, X07 gets a warning (RULE-007 UnitedHealthcare Coding Compliance: an unspecified primary diagnosis, I50.9) and X08 an error (RULE-002 Missing Prior Authorization: a CT with `pa_required` but no authorization number). |
| `claims_upload_with_errors.csv` | 4 claims that can't be saved, each with a different reason: an unregistered patient, an unknown CPT code, a diagnosis with no service line, and a date in the wrong format (16/10/2026 instead of 2026-10-16). |
| `claims_upload_demo_mixed.csv` | 27 claims (34 service lines) for a demo. All 27 save as drafts: 6 pass (D01-D06), 8 get an error (D07-D11 RULE-002 Missing Prior Authorization, D12-D14 RULE-003 no authorization number), 11 get only warnings (D15-D17 RULE-006 Timely Filing, D18-D20 RULE-007 UnitedHealthcare Coding, D21-D22 RULE-010 primary payer missing, D23 RULE-004 High Billed Amount, D24 RULE-009 High-Value Institutional, D27 three warnings), and 2 get an error and two warnings (D25, D26). Service dates are fixed, so D01-D14 and D18-D24 start picking up RULE-006 from 20 November 2026. |
| `claims_demo_10.csv` | 10 claims (16 service lines) for a short demo video, one per department and a different result on each problem claim. 3 pass (V01-V03). 4 get a different error each: V04 RULE-002 Missing Prior Authorization (a brain MRI with no authorization), V05 RULE-011 NCCI edit (therapeutic exercise and manual therapy on the same day with no distinct-service modifier), V06 RULE-012 MUE (3 CBCs, the limit is 2), and V07 RULE-013 Diagnosis Not Covered (an upper GI endoscopy for R10.9 abdominal pain, not on LCD-L33631's list; AI Fix offers the covered codes). 3 get a warning: V08 RULE-007 UnitedHealthcare Coding Compliance (I50.9), V09 RULE-004 High Billed Amount ($35,300), and V10 RULE-014 Diagnosis Doesn't Match Procedure (an echocardiogram whose line points to diabetes, E11.9; AI Fix suggests pointing it at the hypertension, I10, already on the claim). Service dates are 2-6 November 2026, so RULE-006 Timely Filing starts appearing from 3 December 2026; move the dates forward to record after that. Rule IDs are Meridian's. |
| `claims_upload_sample_837P.txt` | An X12 837P with 3 more claims (cardiology, emergency, OB/GYN), as this app writes them at submission (test file). All 3 pass. Patients are matched by name and date of birth, providers by NPI. |

Uploading a file twice creates its claims twice.
