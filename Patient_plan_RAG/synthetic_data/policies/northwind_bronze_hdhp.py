"""Northwind Mutual Health — Bronze HDHP with HSA (2026).

Layout differences from Apex: all-caps headings with different vocabulary
("WHAT YOU PAY", "SERVICES REQUIRING PRECERTIFICATION"), "Plan Number:" and
numeric dates, deductible applies to nearly everything.
"""

SECTIONS = [
    ("PLAN SUMMARY", [
        "Northwind Mutual Health — Bronze HDHP 7000",
        "Plan Number: NWM-BRZ-HSA-7000",
        "Effective Date: 01/01/2026",
        "Expiration Date: 12/31/2026",
        "",
        "Northwind Mutual Health is a fictional insurer used for demonstration "
        "purposes only. This summary does not describe a real policy.",
        "",
        "This is a high-deductible health plan (HDHP) that is eligible for use "
        "with a Health Savings Account (HSA). Except for preventive care, you "
        "pay the full allowed amount for covered services until you meet the "
        "deductible.",
    ]),
    ("WHAT YOU PAY", [
        "Deductible: $7,000 individual / $14,000 family (embedded) per "
        "calendar year, in-network and out-of-network combined.",
        "Out-of-Pocket Maximum: $8,050 individual / $16,100 family per "
        "calendar year.",
        "Coinsurance: After the deductible, the plan pays 100% in-network and "
        "70% out-of-network.",
        "Preventive care: $0, deductible does not apply.",
        "Office visits, urgent care, and emergency room: full allowed amount "
        "until the deductible is met, then $0.",
        "Prescription drugs: full discounted price until the deductible is "
        "met, then $0 for generics and 20% for brand-name drugs.",
    ]),
    ("BENEFITS AT A GLANCE", [
        "Primary and specialist care, including telehealth, are covered after "
        "the deductible. No referrals are needed.",
        "",
        "Emergency services are covered at the in-network level after the "
        "deductible, whether or not the hospital is in-network.",
        "",
        "Diagnostic tests, lab work, and imaging including MRI and CT are "
        "covered after the deductible.",
        "",
        "Outpatient rehabilitation (physical, occupational, speech therapy) is "
        "covered after the deductible for up to 30 visits per calendar year.",
        "",
        "Mental health and substance use disorder services are covered after "
        "the deductible on the same terms as medical services.",
        "",
        "Chiropractic care is covered after the deductible, limited to 12 "
        "visits per calendar year.",
    ]),
    ("SERVICES REQUIRING PRECERTIFICATION", [
        "Precertification must be obtained before the following services. "
        "Claims for services provided without precertification are reduced by "
        "$500.",
        "",
        "• Inpatient admissions (except emergencies; notify within 2 business "
        "days)",
        "• Advanced imaging (MRI, MRA, CT, PET)",
        "• Outpatient surgery in a hospital setting",
        "• Genetic testing",
        "• Infusion therapy",
        "• Specialty medications",
    ]),
    ("LIMITATIONS AND EXCLUSIONS", [
        "The plan does not pay for:",
        "• Cosmetic surgery (unless reconstructive after injury or illness)",
        "• Weight-loss programs and drugs",
        "• Hearing aids",
        "• Routine eye exams and eyewear for adults",
        "• Experimental or investigational services",
        "• Services covered by workers' compensation",
    ]),
    ("COMPLAINTS AND APPEALS", [
        "Members may appeal a denied claim or precertification decision within "
        "180 days. Pre-service appeals are decided within 30 days and "
        "post-service appeals within 60 days. External review is available "
        "after the internal appeal.",
    ]),
    ("DISCLAIMER", [
        "THIS IS A SYNTHETIC INSURANCE POLICY DOCUMENT CREATED FOR "
        "DEMONSTRATION AND TESTING PURPOSES ONLY. Northwind Mutual Health is a "
        "fictional entity. No real insurance coverage, benefits, or "
        "obligations are created by this document.",
    ]),
]


POLICY = {
    "filename": "northwind_bronze_hdhp_2026.pdf",
    "title_lines": [
        ("Northwind Mutual Health", "title"),
        ("Bronze HDHP 7000 with HSA — Summary of Benefits", "subtitle"),
    ],
    "sections": SECTIONS,
}
