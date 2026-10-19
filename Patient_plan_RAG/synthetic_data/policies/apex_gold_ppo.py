"""Apex Health Insurance — Gold PPO (2025). The original demo policy.

Layout: ALL-CAPS section headings, "Label: value" cost lines, bullet list of
prior-authorization services.
"""

SECTIONS = [
    ("PLAN OVERVIEW", [
        "Apex Health Insurance — Gold PPO Plan",
        "Plan ID: AHI-GOLD-2025-PPO",
        "Effective Date: January 1, 2025",
        "Expiration Date: December 31, 2025",
        "",
        "This Summary of Benefits and Coverage (SBC) is provided for "
        "educational and demonstration purposes only. Apex Health Insurance "
        "is a fictional insurer. This document does not constitute a real "
        "insurance policy or guarantee of benefits.",
        "",
        "Plan Type: Preferred Provider Organization (PPO)",
        "Service Area: Nationwide (all 50 states and DC)",
        "Dependents Covered: Spouse, domestic partner, children to age 26",
    ]),
    ("COST-SHARING PROVISIONS", [
        "ANNUAL DEDUCTIBLE",
        "  Individual In-Network: $1,500 per calendar year",
        "  Family In-Network: $3,000 per calendar year",
        "  Individual Out-of-Network: $3,000 per calendar year",
        "  Family Out-of-Network: $6,000 per calendar year",
        "",
        "OUT-OF-POCKET MAXIMUM",
        "  Individual In-Network: $6,000 per calendar year",
        "  Family In-Network: $12,000 per calendar year",
        "  Individual Out-of-Network: $12,000 per calendar year",
        "  Family Out-of-Network: $24,000 per calendar year",
        "  The out-of-pocket maximum includes deductible, copayments, and "
        "coinsurance. Premiums, balance-billed charges, and non-covered "
        "services do not count toward the out-of-pocket maximum.",
        "",
        "COINSURANCE",
        "  In-Network: Plan pays 80%, you pay 20% after deductible",
        "  Out-of-Network: Plan pays 60%, you pay 40% after deductible",
    ]),
    ("COPAYMENTS", [
        "The following copayments apply for in-network services:",
        "",
        "  Primary Care Office Visit: $25 copay (no deductible)",
        "  Specialist Office Visit: $50 copay (no deductible)",
        "  Urgent Care Visit: $75 copay (no deductible)",
        "  Emergency Room Visit: $250 copay (waived if admitted)",
        "  Telehealth Visit: $15 copay (no deductible)",
        "",
        "Out-of-network copayments are 50% higher than listed amounts, "
        "and the deductible applies before copayment.",
    ]),
    ("COVERED SERVICES", [
        "The following services are covered under this plan:",
        "",
        "PREVENTIVE CARE: Covered at 100% in-network with no deductible "
        "or copay. Includes annual wellness exams, immunizations per CDC "
        "schedule, cancer screenings (mammogram, colonoscopy, Pap test), "
        "cholesterol and blood pressure screening, and prenatal care visits.",
        "",
        "INPATIENT HOSPITAL SERVICES: Covered at 80% after deductible "
        "for in-network facilities. Includes room and board, surgical "
        "services, anesthesia, laboratory, imaging, and medically necessary "
        "supplies. Prior authorization is required for all non-emergency "
        "inpatient admissions.",
        "",
        "OUTPATIENT SURGERY: Covered at 80% after deductible in-network. "
        "Prior authorization required for procedures with total expected "
        "charges exceeding $2,000.",
        "",
        "DIAGNOSTIC IMAGING: X-rays covered at 80% after deductible. "
        "Advanced imaging (MRI, CT, PET scan) requires prior authorization "
        "and is covered at 80% after deductible in-network.",
        "",
        "LABORATORY SERVICES: Routine lab work covered at 90% after "
        "deductible in-network. Genetic testing requires prior authorization.",
        "",
        "MENTAL HEALTH AND SUBSTANCE USE DISORDER: Outpatient mental "
        "health visits have a $40 copay. Inpatient mental health and "
        "substance use treatment covered at 80% after deductible. Prior "
        "authorization required for residential treatment programs and "
        "inpatient stays exceeding 7 days.",
        "",
        "REHABILITATION SERVICES: Physical therapy, occupational therapy, "
        "and speech therapy covered at 80% after deductible, limited to 30 "
        "visits per therapy type per calendar year. Prior authorization "
        "required after 12 visits.",
        "",
        "DURABLE MEDICAL EQUIPMENT (DME): Covered at 80% after deductible. "
        "Prior authorization required for items exceeding $500 in cost. "
        "Rental preferred over purchase when appropriate.",
        "",
        "HOME HEALTH CARE: Covered at 80% after deductible, limited to "
        "60 visits per calendar year. Must be ordered by the treating "
        "physician. Prior authorization required.",
        "",
        "SKILLED NURSING FACILITY: Covered at 80% after deductible, "
        "limited to 60 days per calendar year. Requires prior authorization. "
        "Must follow a qualifying inpatient hospital stay of at least 3 days.",
        "",
        "HOSPICE CARE: Covered at 100% in-network. No deductible or "
        "copay. Requires physician certification of terminal illness with "
        "life expectancy of 6 months or less.",
        "",
        "MATERNITY AND NEWBORN CARE: Prenatal visits covered under "
        "preventive care. Delivery and postnatal care covered at 80% "
        "after deductible. Newborn care covered from birth.",
    ]),
    ("PRESCRIPTION DRUG COVERAGE", [
        "Prescription drugs are covered through the Apex Health Pharmacy "
        "Benefit. Formulary tiers:",
        "",
        "  Tier 1 (Generic): $10 copay",
        "  Tier 2 (Preferred Brand): $35 copay",
        "  Tier 3 (Non-Preferred Brand): $70 copay",
        "  Tier 4 (Specialty): 25% coinsurance, maximum $250 per fill",
        "",
        "Mail-order prescriptions (90-day supply): 2.5x retail copay",
        "Prior authorization required for Tier 4 specialty medications "
        "and select Tier 3 medications. Step therapy may apply.",
        "",
        "Annual prescription drug out-of-pocket maximum: $2,500 individual / "
        "$5,000 family (separate from medical out-of-pocket maximum).",
    ]),
    ("PRIOR AUTHORIZATION REQUIREMENTS", [
        "The following services require prior authorization before "
        "treatment. Failure to obtain prior authorization may result in "
        "denial of the claim or reduced benefits (50% penalty).",
        "",
        "Services Requiring Prior Authorization:",
        "  • All non-emergency inpatient hospital admissions",
        "  • Outpatient surgery with expected charges exceeding $2,000",
        "  • Advanced diagnostic imaging (MRI, CT scan, PET scan)",
        "  • Genetic testing",
        "  • Physical, occupational, or speech therapy after 12 visits",
        "  • Durable medical equipment exceeding $500",
        "  • Home health care services",
        "  • Skilled nursing facility care",
        "  • Residential mental health or substance use treatment",
        "  • Inpatient mental health stays exceeding 7 days",
        "  • Tier 4 specialty medications",
        "  • Select Tier 3 medications (see formulary)",
        "  • Transplant services",
        "  • Bariatric surgery",
        "",
        "Prior Authorization Process:",
        "The ordering provider must submit the authorization request "
        "with the following documentation:",
        "  1. Completed Prior Authorization Request Form (Form PA-100)",
        "  2. Clinical notes supporting medical necessity",
        "  3. CPT/HCPCS procedure code(s)",
        "  4. ICD-10 diagnosis code(s)",
        "  5. Provider NPI number",
        "  6. Letter of Medical Necessity (for complex cases)",
        "",
        "Authorization decisions are made within 5 business days for "
        "standard requests and 72 hours for urgent requests. A peer-to-peer "
        "review with the plan medical director may be requested if the "
        "initial authorization is denied.",
        "",
        "Emergency Admissions: Prior authorization is not required for "
        "emergency admissions. However, notification must be provided "
        "within 48 hours of the admission.",
    ]),
    ("EXCLUSIONS AND LIMITATIONS", [
        "The following services are NOT covered under this plan:",
        "",
        "  • Cosmetic surgery or procedures (unless medically necessary "
        "due to injury, disease, or congenital defect)",
        "  • Experimental or investigational treatments not approved by FDA",
        "  • Long-term custodial care",
        "  • Services received outside the United States (except emergency)",
        "  • Weight loss programs and supplements (unless part of approved "
        "bariatric surgery program)",
        "  • Acupuncture, naturopathy, and homeopathy",
        "  • Dental services (covered under separate dental plan)",
        "  • Routine vision care (covered under separate vision plan)",
        "  • Hearing aids for adults over age 18",
        "  • Private duty nursing",
        "  • Non-emergency ambulance transportation",
        "  • Reversal of elective sterilization",
    ]),
    ("NETWORK PROVISIONS", [
        "IN-NETWORK PROVIDERS: Members receive the highest level of "
        "benefits when using in-network providers. In-network providers "
        "have agreed to negotiated rates and will not balance-bill members.",
        "",
        "OUT-OF-NETWORK PROVIDERS: Members may use out-of-network "
        "providers at higher cost-sharing levels. Out-of-network providers "
        "may balance-bill for charges exceeding the plan's allowed amount.",
        "",
        "REFERRAL REQUIREMENTS: This PPO plan does not require referrals "
        "to see in-network specialists. However, the plan recommends "
        "coordination through a primary care provider for optimal care.",
        "",
        "EMERGENCY SERVICES: Emergency services are covered at in-network "
        "rates regardless of whether the provider is in-network or "
        "out-of-network, per the No Surprises Act.",
    ]),
    ("APPEALS AND GRIEVANCES", [
        "Members have the right to appeal any adverse benefit determination. "
        "Appeals must be filed within 180 days of receiving the denial notice.",
        "",
        "Internal Appeal: Reviewed by a physician not involved in the "
        "original decision. Decision within 30 days (72 hours for urgent).",
        "",
        "External Review: If internal appeal is denied, members may "
        "request an independent external review within 4 months.",
        "",
        "Grievances: Non-coverage complaints may be filed at any time "
        "and will be acknowledged within 5 business days.",
    ]),
    ("COORDINATION OF BENEFITS", [
        "When a member is covered by more than one health plan, this plan "
        "coordinates benefits with the other plan(s) to prevent duplicate "
        "payment. The Birthday Rule determines primary/secondary status "
        "for dependent children.",
    ]),
    ("DEFINITIONS", [
        "Allowed Amount: The maximum amount the plan will pay for a covered "
        "service based on negotiated rates or usual and customary charges.",
        "",
        "Balance Billing: When an out-of-network provider bills the member "
        "for the difference between their charge and the plan's allowed amount.",
        "",
        "Coinsurance: The percentage of costs a member pays after the "
        "deductible has been met.",
        "",
        "Copayment: A fixed dollar amount a member pays for a covered "
        "service at the time of service.",
        "",
        "Deductible: The amount a member pays for covered services before "
        "the plan begins to pay.",
        "",
        "Medical Necessity: Services that are clinically appropriate in "
        "terms of type, frequency, extent, and duration, and considered "
        "effective for the patient's illness, injury, or disease.",
        "",
        "Out-of-Pocket Maximum: The most a member pays during a plan year "
        "before the plan begins to pay 100% of covered services.",
        "",
        "Prior Authorization: Approval required from the plan before "
        "receiving certain services to confirm medical necessity and "
        "coverage eligibility.",
    ]),
    ("DISCLAIMER", [
        "THIS IS A SYNTHETIC INSURANCE POLICY DOCUMENT CREATED FOR "
        "DEMONSTRATION AND TESTING PURPOSES ONLY. Apex Health Insurance "
        "is a fictional entity. No real insurance coverage, benefits, or "
        "obligations are created by this document.",
        "",
        "Do not use this document to make real healthcare or financial "
        "decisions. Always consult your actual insurance policy and plan "
        "administrator for coverage information.",
    ]),
]


POLICY = {
    "filename": "apex_health_gold_ppo_2025.pdf",
    "title_lines": [
        ("Apex Health Insurance", "title"),
        ("Gold PPO Plan — Summary of Benefits and Coverage", "subtitle"),
        ("Plan Year 2025 | Plan ID: AHI-GOLD-2025-PPO", "body"),
    ],
    "sections": SECTIONS,
}
