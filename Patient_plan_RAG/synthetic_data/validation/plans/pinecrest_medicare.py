"""Pinecrest Health — Pinecrest Senior Care HMO, a Medicare Advantage plan (2026).

Style: an "Evidence of Coverage" with numbered chapters and a medical
benefits chart. Nuances: no medical deductible but a maximum out-of-pocket
amount; per-day inpatient copays; referrals from the PCP; "prior
authorization (approval in advance)"; a drug deductible that applies to
some tiers only; supplemental dental, vision and hearing allowances.
"""

POLICY = {
    "filename": "pinecrest_senior_care_hmo_2026.pdf",
    "title_lines": [
        ("January 1 – December 31, 2026", "body"),
        ("Evidence of Coverage:", "subtitle"),
        ("Your Medicare Health Benefits and Services and Prescription Drug Coverage as a Member "
         "of Pinecrest Senior Care HMO", "title"),
        ("Pinecrest Health | Plan contract number H9917-004", "body"),
        ("Pinecrest Health is a fictional organization used for testing. This document does not "
         "describe a real Medicare plan.", "body"),
    ],
    "sections": [
        ("Chapter 1: Getting started as a member", [
            "Pinecrest Senior Care HMO is a Medicare Advantage health maintenance organization. "
            "You must continue to pay your Medicare Part B premium. The plan premium is $0 per "
            "month.",
            "You must use network providers except for emergency care, urgent care when you are "
            "outside the service area, and out-of-area dialysis.",
        ]),
        ("Chapter 4: Medical Benefits Chart (what is covered and what you pay)", [
            "This plan has no medical deductible. Your maximum out-of-pocket amount for covered "
            "Part A and Part B services from network providers is $5,900 per year. After you "
            "reach it, you pay nothing for covered medical services for the rest of the year.",
            "",
            {"table": [
                ["Services that are covered for you", "What you must pay"],
                ["Primary care provider visits", "$0 copay"],
                ["Specialist visits (referral from your PCP required)", "$35 copay"],
                ["Inpatient hospital care (prior authorization required)",
                 "$325 copay per day for days 1–5; $0 per day for days 6–90"],
                ["Outpatient surgery (prior authorization required)", "$250 copay"],
                ["Diagnostic radiology: MRI, CT, PET (prior authorization required)", "$150 copay"],
                ["Lab services", "$0 copay"],
                ["Emergency care", "$110 copay, waived if admitted within 24 hours"],
                ["Urgently needed services", "$45 copay"],
                ["Skilled nursing facility (prior authorization required)",
                 "$0 per day for days 1–20; $203 per day for days 21–100"],
                ["Physical therapy", "$30 copay per visit"],
                ["Ambulance", "$275 copay per one-way trip"],
            ]},
            "",
            "Prior authorization means approval in advance: your provider must get approval "
            "from Pinecrest before you receive the service. Pinecrest decides standard requests "
            "within 14 days and expedited requests within 72 hours.",
        ]),
        ("Chapter 4, Section 2.2: Extra benefits", [
            "Dental: two cleanings and exams per year at $0; comprehensive dental services up to "
            "a $1,500 annual maximum.",
            "Vision: one routine eye exam per year at $0 and a $200 allowance for eyewear every "
            "year.",
            "Hearing: one routine hearing exam per year at $0; hearing aids at $499 or $799 per "
            "aid, up to two aids per year.",
            "Fitness: a gym membership at participating fitness centers at no cost.",
        ]),
        ("Chapter 4, Section 3: Services that are not covered (exclusions)", [
            "• Cosmetic surgery, except after an accidental injury or to improve a malformed body "
            "part",
            "• Custodial care in a nursing home",
            "• Routine foot care, except for members with diabetes or certain other conditions",
            "• Experimental medical procedures",
            "• Private room in a hospital, unless medically necessary",
        ]),
        ("Chapter 6: What you pay for your Part D prescription drugs", [
            "The drug deductible is $250 and applies to Tier 3, Tier 4 and Tier 5 drugs only. "
            "Tier 1 and Tier 2 drugs are not subject to the deductible.",
            {"table": [
                ["Tier", "30-day supply at a preferred pharmacy"],
                ["Tier 1 (preferred generic)", "$0"],
                ["Tier 2 (generic)", "$8"],
                ["Tier 3 (preferred brand)", "$45"],
                ["Tier 4 (non-preferred drug)", "40% coinsurance"],
                ["Tier 5 (specialty)", "33% coinsurance"],
            ]},
        ]),
        ("Chapter 9: If you have a problem or complaint", [
            "You can ask for a coverage decision or make an appeal. You must make your appeal "
            "within 65 calendar days of the date on the coverage decision letter.",
        ]),
    ],
}
