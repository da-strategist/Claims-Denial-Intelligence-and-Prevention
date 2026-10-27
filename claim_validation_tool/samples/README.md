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
| `claims_upload_sample_837P.txt` | An X12 837P with 3 more claims (cardiology, emergency, OB/GYN), as this app writes them at submission (test file). All 3 pass. Patients are matched by name and date of birth, providers by NPI. |

Uploading a file twice creates its claims twice.
