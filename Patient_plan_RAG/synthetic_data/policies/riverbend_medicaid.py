"""Riverbend Community Care — Medicaid managed care handbook (2025-26).

Layout differences from Apex: plain-language member handbook with headings
phrased as questions, near-zero cost sharing, "Issued by:" instead of an
insurer line, state-fiscal-year dates.
"""

SECTIONS = [
    ("About This Handbook", [
        "Issued by: Riverbend Community Health Plan",
        "Program: Riverbend Community Care (Medicaid managed care)",
        "Plan ID: RCHP-MCD-2025",
        "Effective Date: July 1, 2025",
        "End Date: June 30, 2026",
        "",
        "Riverbend Community Health Plan is a fictional Medicaid health plan "
        "created for demonstration purposes. This handbook does not describe "
        "real benefits.",
    ]),
    ("How much will I pay?", [
        "Most services cost you nothing. There is no monthly premium and no "
        "deductible.",
        "Prescription drugs: $1 for generic drugs and $3 for brand-name drugs.",
        "Emergency room visits that are not emergencies: $8.",
        "Children under 19 and pregnant members pay $0 for everything.",
    ]),
    ("What does my plan cover?", [
        "Doctor visits, including visits to specialists your primary care "
        "provider sends you to.",
        "Check-ups, shots, and screenings for adults and children.",
        "Hospital care and emergency care, 24 hours a day.",
        "Lab tests and X-rays. MRIs and CT scans are covered when your doctor "
        "gets approval first.",
        "Pregnancy care, delivery, and care after your baby is born.",
        "Mental health and substance use care, including counseling.",
        "Dental care for members under 21, and emergency dental care for "
        "adults.",
        "Eye exams and glasses once a year for members under 21.",
        "Rides to medical appointments at no cost. Call Member Services at "
        "least 2 days ahead.",
    ]),
    ("Do I need a referral?", [
        "Yes, for most specialists. Ask your primary care provider (PCP) for a "
        "referral. You do not need a referral for family planning, women's "
        "health care, behavioral health, or emergencies.",
    ]),
    ("When do I need approval first?", [
        "Your doctor must ask us for approval (prior authorization) before you "
        "get:",
        "• MRI, CT, and PET scans",
        "• Planned surgery and hospital stays",
        "• Home health care",
        "• Medical equipment such as wheelchairs and hospital beds",
        "• Some medicines (see the Preferred Drug List)",
        "",
        "We decide most requests within 14 days, or within 72 hours if waiting "
        "could hurt your health.",
    ]),
    ("What is not covered?", [
        "• Cosmetic surgery",
        "• Fertility treatment",
        "• Experimental treatments",
        "• Services from providers who do not accept Medicaid",
        "• Adult routine dental cleanings",
    ]),
    ("What if I disagree with a decision?", [
        "You can ask for an appeal within 60 days of the date on the notice. "
        "We will decide within 30 days, or 72 hours for urgent cases. If you "
        "still disagree, you can ask for a State Fair Hearing within 120 days "
        "of our appeal decision.",
    ]),
    ("DISCLAIMER", [
        "THIS IS A SYNTHETIC INSURANCE POLICY DOCUMENT CREATED FOR "
        "DEMONSTRATION AND TESTING PURPOSES ONLY. Riverbend Community Health "
        "Plan is a fictional entity. No real insurance coverage, benefits, or "
        "obligations are created by this document.",
    ]),
]


POLICY = {
    "filename": "riverbend_community_care_medicaid_2025.pdf",
    "title_lines": [
        ("Riverbend Community Care", "title"),
        ("Member Handbook", "subtitle"),
    ],
    "sections": SECTIONS,
}
