"""Summit Care Health Plan — Silver HMO (2026).

Layout differences from Apex: title-case numbered section headings
("Section 3 – Covered Benefits"), copays in a table instead of "Label: $X"
lines, referrals required, exclusions under "Services We Do Not Cover".
"""

SECTIONS = [
    ("Section 1 – Plan Information", [
        "Insurer: Summit Care Health Plan, Inc.",
        "Plan Name: Silver HMO Value",
        "Plan ID: SCH-SLV-HMO-26",
        "Effective Date: January 1, 2026",
        "Expiration Date: December 31, 2026",
        "",
        "Summit Care Health Plan is a fictional health maintenance organization "
        "created for demonstration purposes. This booklet does not describe a "
        "real insurance product.",
        "",
        "Plan Type: Health Maintenance Organization (HMO)",
        "Service Area: Front Range counties of Colorado",
        "Network: Summit Care Select network only (no out-of-network benefits "
        "except emergencies)",
    ]),
    ("Section 2 – Your Costs", [
        "Annual deductible: $2,500 individual / $5,000 family. The deductible "
        "does not apply to office visits, generic drugs, or preventive care.",
        "Out-of-pocket limit: $8,000 individual / $16,000 family per plan year.",
        "Coinsurance after deductible: you pay 30%.",
        "",
        "Copays for in-network services:",
        {"table": [
            ["Service", "You pay", "Deductible applies?"],
            ["Primary care visit", "$30 copay", "No"],
            ["Specialist visit (with referral)", "$65 copay", "No"],
            ["Urgent care center", "$90 copay", "No"],
            ["Emergency room", "$400 copay", "Yes"],
            ["Virtual visit", "$0", "No"],
            ["Generic drugs (30-day)", "$15 copay", "No"],
            ["Preferred brand drugs (30-day)", "$60 copay", "Yes"],
        ]},
    ]),
    ("Section 3 – Covered Benefits", [
        "When you use Summit Care Select providers, the plan covers:",
        "",
        "Preventive services such as annual physicals, well-child visits, "
        "vaccines, and recommended cancer screenings are covered at no cost.",
        "",
        "Hospital stays are covered at 70% after the deductible. Your primary "
        "care provider or treating specialist must arrange non-emergency "
        "admissions.",
        "",
        "Imaging: X-rays and ultrasounds are covered at 70% after the "
        "deductible. MRI, CT, and nuclear medicine scans also need advance "
        "approval (see Section 5).",
        "",
        "Physical, occupational, and speech therapy are covered at 70% after "
        "the deductible, up to 20 combined visits per plan year.",
        "",
        "Behavioral health: outpatient therapy visits cost a $30 copay, the "
        "same as a primary care visit. Inpatient behavioral health is covered "
        "at 70% after the deductible.",
        "",
        "Maternity care is covered at 70% after the deductible; prenatal "
        "visits are covered as preventive care.",
    ]),
    ("Section 4 – Referrals and Your Primary Care Provider", [
        "Every member must choose a primary care provider (PCP) from the Summit "
        "Care Select network. You need a referral from your PCP before seeing "
        "a specialist, except for OB-GYN care, behavioral health, and "
        "emergencies. Without a referral, specialist visits are not covered.",
    ]),
    ("Section 5 – Services That Need Advance Approval", [
        "Your provider must get approval from Summit Care before you receive "
        "these services. If approval is not obtained, the service will not be "
        "covered.",
        "",
        "• Planned hospital admissions and surgery",
        "• MRI, CT, PET, and nuclear medicine scans",
        "• Therapy visits beyond the first 10 in a plan year",
        "• Home health care and hospice",
        "• Durable medical equipment over $1,000",
        "• Specialty drugs",
        "",
        "Standard requests are decided within 7 calendar days; urgent requests "
        "within 72 hours.",
    ]),
    ("Services We Do Not Cover", [
        "• Care from providers outside the Summit Care Select network "
        "(except emergencies)",
        "• Cosmetic procedures",
        "• Infertility treatment",
        "• Long-term care",
        "• Routine foot care",
        "• Bariatric surgery",
        "• Adult dental and vision care",
    ]),
    ("Section 6 – Appeals", [
        "If we deny a claim or an approval request, you may file an appeal "
        "within 180 days of the denial. We will decide standard appeals within "
        "30 days and urgent appeals within 72 hours. You may then request an "
        "independent external review.",
    ]),
    ("DISCLAIMER", [
        "THIS IS A SYNTHETIC INSURANCE POLICY DOCUMENT CREATED FOR "
        "DEMONSTRATION AND TESTING PURPOSES ONLY. Summit Care Health Plan is a "
        "fictional entity. No real insurance coverage, benefits, or "
        "obligations are created by this document.",
    ]),
]


POLICY = {
    "filename": "summit_care_silver_hmo_2026.pdf",
    "title_lines": [
        ("Summit Care Health Plan", "title"),
        ("Member Benefits Booklet — Plan Year 2026", "subtitle"),
    ],
    "sections": SECTIONS,
}
