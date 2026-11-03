# Validation set — review sheet

Please check each **expected answer** against the plan documents in `data/validation/`. Mark anything you disagree with, or that an experienced reader would interpret differently, and add a note. Nuance questions matter most. The app has **not** been run on these yet; it will be scored only after your review.

Columns: what the person asks · the answer the app should give · where it is in the document · what makes it tricky. "Not in the document" means the app should say it can't find the answer rather than guess.

## Plan details the app should read from each document

| Document | Insurer | Plan | Plan ID | Effective | Ends | Note |
|---|---|---|---|---|---|---|
| cedar_valley_silver_3500_2026.pdf | Cedar Valley Health Plan | Cedar Silver 3500 | CVH-SLV-3500-26 | 2026-01-01 | 2026-12-31 |  |
| harborview_gold_epo_2025.pdf | Harborview Health Partners | Gold EPO 1000 | HHP-EPO-1000-2025 | 2025-01-01 | 2025-12-31 |  |
| harborview_gold_epo_2026.pdf | Harborview Health Partners | Gold EPO 1000 | HHP-EPO-1000-2026 | 2026-01-01 | 2026-12-31 |  |
| pinecrest_senior_care_hmo_2026.pdf | Pinecrest Health | Pinecrest Senior Care HMO | H9917-004 | 2026-01-01 | 2026-12-31 | Plan ID: the Medicare contract number. |
| lakeshore_student_health_2025.pdf | Bayfront Life & Health Insurance Company | Student Health Insurance Plan | BLH-SHIP-2025 | 2025-08-15 | 2026-08-14 | Insurer: the underwriter (Bayfront) rather than the university. Plan name could also be read as 'Lakeshore University Student Health Insurance Plan'. |
| meridian_catastrophic_2026.pdf | Meridian Health Cooperative | Catastrophic Shield 10150 | MHC-CAT-10150 | 2026-01-01 | 2026-12-31 |  |
| meridian_catastrophic_2026_scanned.pdf | Meridian Health Cooperative | Catastrophic Shield 10150 | MHC-CAT-10150 | 2026-01-01 | 2026-12-31 |  |

## Cedar Valley Health Plan — Cedar Silver 3500 (SBC format)

| ID | Question | Expected answer | Where | Type | Tricky because | Agree? |
|---|---|---|---|---|---|---|
| CV-01 | What is the deductible? | $3,500 individual / $7,000 family. | Important Questions | Look-up |  | |
| CV-02 | If only my child has medical bills, does the plan start paying once my child reaches $3,500? | No. The deductible is non-embedded: the whole $7,000 family deductible must be met first. | Important Questions | Nuance | Non-embedded family deductible. | |
| CV-03 | Do I have to meet the deductible before a primary care visit? | No. Primary care is a $30 copay per visit and the deductible does not apply. | Common Medical Event, Important Questions | Nuance | Copay before the deductible. | |
| CV-04 | How much is a specialist visit? | $75 copay per visit after the deductible; a referral is required. | Common Medical Event | Nuance | Unlike primary care, the specialist copay applies only after the deductible. | |
| CV-05 | Do I need a referral to see a specialist? | Yes, a written referral from your primary care provider. | Important Questions | Look-up |  | |
| CV-06 | Does an MRI need preauthorization? | Yes. 20% coinsurance in network; without preauthorization benefits are reduced by 50% of the allowed amount, up to $1,000. | Common Medical Event | Look-up |  | |
| CV-07 | Does an MRI need prior authorization? | Yes (the plan calls it preauthorization); without it benefits are reduced by 50%, up to $1,000. | Common Medical Event | Nuance | The plan says 'preauthorization', the question says 'prior authorization'. | |
| CV-08 | What is the out-of-pocket limit? | $8,000 individual / $16,000 family. | Important Questions | Look-up |  | |
| CV-09 | Is out-of-network care covered? | Yes, at 50% coinsurance after the deductible. | Important Questions | Look-up |  | |
| CV-10 | How much is an emergency room visit? | $400 copay per visit, then 20% coinsurance; the copay is waived if you are admitted. | Common Medical Event | Look-up |  | |
| CV-11 | How many physical therapy visits are covered? | 20 visits per year for physical, occupational and speech therapy combined. | Common Medical Event | Nuance | The limit is shared across three therapies. | |
| CV-12 | Is acupuncture covered? | No, it is excluded. | Excluded Services | Look-up |  | |
| CV-13 | Are children's glasses covered? | No. A children's eye exam is covered once a year, but glasses are not. | Common Medical Event | Nuance | Exam covered, glasses not. | |
| CV-14 | How many chiropractic visits are covered? | 12 visits per year. | Other Covered Services, Excluded Services | Look-up |  | |
| CV-15 | How long does a preauthorization decision take? | 15 days for standard requests, 72 hours for urgent requests. | Appeals, Your Rights | Look-up |  | |
| CV-16 | Do penalties for missing preauthorization count toward the out-of-pocket limit? | No, they are not included in the out-of-pocket limit. | Important Questions | Nuance |  | |
| CV-17 | What is my monthly premium? | Not stated in this document. | — | Not in the document |  | |
| CV-18 | Does the plan pay for gym memberships? | Not stated in this document. | — | Not in the document |  | |
| CV-19 | Is LASIK eye surgery covered? | Not stated in this document. | — | Not in the document | Cosmetic surgery is excluded, but LASIK is not mentioned. | |

## Harborview Health Partners — Gold EPO 1000, 2026 booklet

| ID | Question | Expected answer | Where | Type | Tricky because | Agree? |
|---|---|---|---|---|---|---|
| HV-01 | What is the deductible? | $1,000 per person, $2,000 per family. | Your Costs | Look-up |  | |
| HV-02 | Once one family member meets their own deductible, does the plan start paying for them? | Yes. The deductible is embedded. | Your Costs | Nuance | Embedded deductible (the opposite of Cedar Valley). | |
| HV-03 | How much is a specialist visit? | $45 copay, deductible waived. | Your Costs | Look-up |  | |
| HV-04 | Is out-of-network care covered? | No. It's an EPO: out-of-network providers are not covered except emergency care and urgent care when traveling outside the service area. | Using the Network | Nuance | EPO rules. | |
| HV-05 | Do I need a referral to see a specialist? | No referral is needed for a network specialist. | Using the Network | Look-up |  | |
| HV-06 | Does an MRI need prior authorization? | Yes. The plan calls it prior approval. | Prior Approval | Nuance | The plan says 'prior approval'. | |
| HV-07 | How long does Harborview take to decide a prior approval request? | 15 calendar days for standard requests, 72 hours for urgent requests. | Prior Approval | Look-up |  | |
| HV-08 | How many physical therapy visits can I get? | Up to 25 visits per condition per calendar year. | What Is Covered | Nuance | Limit per condition, not per year overall. | |
| HV-09 | Is bariatric surgery covered? | No, it is excluded. | What Is Not Covered | Look-up |  | |
| HV-10 | How much is the emergency room? | $250 copay, waived if admitted. | Your Costs | Look-up |  | |
| HV-11 | What do specialty drugs cost? | 30% up to $250 per fill. | What Is Covered | Look-up |  | |
| HV-12 | Can I get a sleep study without approval? | No, sleep studies need prior approval. | Prior Approval | Look-up |  | |
| HV-13 | What is the out-of-pocket maximum? | $4,500 per person, $9,000 per family. | Your Costs | Look-up |  | |
| HV-14 | Does the plan cover travel vaccines? | Not stated in this document. | — | Not in the document |  | |
| HV-15 | What is the copay for an ambulance? | Not stated in this document. | — | Not in the document |  | |

## Pinecrest Senior Care HMO (Medicare Advantage)

| ID | Question | Expected answer | Where | Type | Tricky because | Agree? |
|---|---|---|---|---|---|---|
| PC-01 | What is the deductible? | There is no medical deductible (maximum out-of-pocket $5,900); the drug deductible is $250 for Tiers 3–5. | Medical Benefits Chart | Nuance | No medical deductible, but a separate drug deductible. | |
| PC-02 | What is the maximum out-of-pocket amount? | $5,900 per year in network. | Medical Benefits Chart | Look-up |  | |
| PC-03 | How much does a specialist visit cost? | $35 copay; a referral from your PCP is required. | Medical Benefits Chart | Look-up |  | |
| PC-04 | What would a 7-day hospital stay cost? | $325 per day for days 1–5 ($1,625), then $0 for days 6–7; prior authorization required. | Medical Benefits Chart | Nuance | Per-day copay tiers. | |
| PC-05 | Does an MRI need prior authorization? | Yes; $150 copay. | Medical Benefits Chart | Look-up |  | |
| PC-06 | Do I need approval in advance for outpatient surgery? | Yes, prior authorization is required; $250 copay. | Medical Benefits Chart | Nuance | 'Approval in advance' wording. | |
| PC-07 | Does the drug deductible apply to generic drugs? | No. It applies to Tiers 3, 4 and 5 only; Tier 1 and Tier 2 are not subject to it. | Part D | Nuance |  | |
| PC-08 | Are hearing aids covered? | Yes: $499 or $799 per aid, up to two aids per year. | Extra benefits | Look-up |  | |
| PC-09 | How much dental coverage is there? | Two cleanings and exams per year at $0; comprehensive dental up to a $1,500 annual maximum. | Extra benefits | Look-up |  | |
| PC-10 | Is routine foot care covered? | Not covered, except for members with diabetes or certain other conditions. | not covered, exclusions | Nuance | Exception inside an exclusion. | |
| PC-11 | Do I still pay my Part B premium? | Yes. | Getting started | Look-up |  | |
| PC-12 | How long do I have to file an appeal? | 65 calendar days. | problem or complaint | Look-up |  | |
| PC-13 | What do skilled nursing days 21 to 100 cost? | $203 per day. | Medical Benefits Chart | Look-up |  | |
| PC-14 | How much is a Tier 2 drug? | $8 for a 30-day supply at a preferred pharmacy. | Part D | Look-up |  | |
| PC-15 | Does the plan cover acupuncture? | Not stated in this document. | — | Not in the document |  | |
| PC-16 | Is there a monthly allowance for over-the-counter items? | Not stated in this document. | — | Not in the document |  | |

## Lakeshore University Student Health Insurance Plan (two columns, footnotes)

| ID | Question | Expected answer | Where | Type | Tricky because | Agree? |
|---|---|---|---|---|---|---|
| LS-01 | What is the deductible? | $250 in network, $500 out of network, per policy year. | What You Pay | Look-up |  | |
| LS-02 | Do I pay the deductible at the Student Health Center? | No. Visits there are no charge and the deductible does not apply. | What You Pay | Nuance | Stated in a footnote as well. | |
| LS-03 | How many free counseling sessions do I get? | The first 12 sessions per policy year at the University Counseling Center, then $20 each. | Mental Health | Look-up |  | |
| LS-04 | Do sessions with an off-campus therapist count toward the free sessions? | No. | Mental Health | Nuance | Only in a footnote. | |
| LS-05 | Does an MRI need prior authorization? | Yes (pre-certification); benefits are reduced by 20% without it. | Pre-Certification | Nuance | 'Pre-certification' wording. | |
| LS-06 | I was injured playing on the university soccer team. Is that covered? | No. Injuries from intercollegiate sports are excluded. | Exclusions | Nuance | The question doesn't use the word 'intercollegiate'. | |
| LS-07 | Are dental cleanings covered? | No. Only injury to sound natural teeth is covered, up to $500 per accident. | Covered Benefits | Nuance | Only in a footnote. | |
| LS-08 | How many physical therapy visits are covered? | Up to 30 visits per policy year at 20% coinsurance. | Covered Benefits | Look-up |  | |
| LS-09 | When does the policy year end? | August 14, 2026. | Lakeshore, Student Health | Look-up |  | |
| LS-10 | How long do I have to file a claim? | 90 days from the date of service. | Claims and Appeals | Look-up |  | |
| LS-11 | How much is the emergency room? | $150 copay, then coinsurance; waived if admitted. | What You Pay | Look-up |  | |
| LS-12 | Can I add my spouse to the plan? | Yes; spouses and children under 26 may be added. | Who Is Covered | Look-up |  | |
| LS-13 | Does the plan cover me while studying abroad? | Not stated in this document. | — | Not in the document |  | |
| LS-14 | How much does the plan cost per semester? | Not stated in this document. | — | Not in the document |  | |

## Meridian Catastrophic Shield 10150 (text PDF)

| ID | Question | Expected answer | Where | Type | Tricky because | Agree? |
|---|---|---|---|---|---|---|
| MD-01 | What is the deductible? | $10,150 per person, the same as the out-of-pocket maximum. | What you pay | Nuance | Deductible equals the out-of-pocket maximum. | |
| MD-02 | Are any doctor visits covered before the deductible? | Yes: three primary care visits per year at a $40 copay, plus preventive care at no cost. | What you pay | Nuance |  | |
| MD-03 | Is a specialist visit covered before the deductible? | No; you pay in full until the deductible is met. | What you pay | Look-up |  | |
| MD-04 | Does a planned hospital stay need prior authorization? | Yes; the plan calls it pre-service review. | Pre-service review | Nuance | 'Pre-service review': wording the app has never seen. | |
| MD-05 | Is bariatric surgery covered? | It needs pre-service review; surgery is covered after the deductible. | Pre-service review | Nuance | Coverage is implied (surgery covered) rather than stated for bariatric surgery. | |
| MD-06 | Who can enroll in this plan? | People under 30, or of any age with a hardship or affordability exemption. | Who can enroll | Look-up |  | |
| MD-07 | Are hearing aids covered? | No. | Not covered | Look-up |  | |
| MD-08 | How many rehabilitation visits are covered? | 20 visits per year. | Covered services | Look-up |  | |
| MD-09 | Does the plan come with a health savings account? | Not stated in this document. | — | Not in the document |  | |
| MD-10 | Is chiropractic care covered? | Not stated in this document. | — | Not in the document |  | |

## Meridian Catastrophic Shield 10150 (scanned copy, read by OCR)

| ID | Question | Expected answer | Where | Type | Tricky because | Agree? |
|---|---|---|---|---|---|---|
| MS-01 | What is the deductible? | $10,150 per person. | What you pay | Scanned |  | |
| MS-02 | Are any doctor visits covered before the deductible? | Three primary care visits per year at a $40 copay. | What you pay | Scanned |  | |
| MS-03 | Does a planned hospital stay need prior authorization? | Yes, pre-service review. | Pre-service review | Scanned |  | |
| MS-04 | How many rehabilitation visits are covered? | 20 visits per year. | Covered services | Scanned |  | |
| MS-05 | Are hearing aids covered? | No. | Not covered | Scanned |  | |
| MS-06 | Who can enroll in this plan? | Under 30, or with an exemption. | Who can enroll | Scanned |  | |

## People with several plans

| ID | Question | Expected answer | Where | Type | Tricky because | Agree? |
|---|---|---|---|---|---|---|
| MP-01 | What is my deductible? | Both booklets shown separately: $750 per person (2025) and $1,000 per person (2026); the difference is flagged. | harborview_gold_epo_2025 + harborview_gold_epo_2026 | Several plans | Same plan, two plan years: one is out of date. | |
| MP-02 | How much is a specialist visit? | $40 (2025) and $45 (2026), shown separately and flagged. | harborview_gold_epo_2025 + harborview_gold_epo_2026 | Several plans |  | |
| MP-03 | What is the deductible in the 2026 booklet? | $1,000 per person (2026 only). | harborview_gold_epo_2025 + harborview_gold_epo_2026 | Several plans | Both booklets have the same plan name; only the year differs. | |
| MP-04 | Does an MRI need prior approval? | Yes, in both years. | harborview_gold_epo_2025 + harborview_gold_epo_2026 | Several plans |  | |
| MP-05 | What is my deductible? | Cedar Silver 3500: $3,500 individual / $7,000 family. Pinecrest: no medical deductible. Shown separately. | cedar_valley_silver_3500_2026 + pinecrest_senior_care_hmo_2026 | Several plans |  | |
| MP-06 | How much is a specialist visit under Cedar Silver 3500? | $75 copay after the deductible (Cedar only). | cedar_valley_silver_3500_2026 + pinecrest_senior_care_hmo_2026 | Several plans |  | |
| MP-07 | Do I need a referral to see a specialist? | Yes under both plans. | cedar_valley_silver_3500_2026 + pinecrest_senior_care_hmo_2026 | Several plans |  | |
| MP-08 | What is the out-of-pocket maximum? | Lakeshore: $6,350 per insured person; Meridian: $10,150. Flagged as different. | lakeshore_student_health_2025 + meridian_catastrophic_2026 | Several plans |  | |
| MP-09 | Is physical therapy limited? | Lakeshore: up to 30 visits per policy year. Meridian: rehabilitation limited to 20 visits per year. | lakeshore_student_health_2025 + meridian_catastrophic_2026 | Several plans |  | |
| MP-10 | How much is the emergency room under Catastrophic Shield 10150? | Covered after the deductible; you pay in full until the $10,150 deductible is met (Meridian only). | lakeshore_student_health_2025 + meridian_catastrophic_2026 | Several plans |  | |
