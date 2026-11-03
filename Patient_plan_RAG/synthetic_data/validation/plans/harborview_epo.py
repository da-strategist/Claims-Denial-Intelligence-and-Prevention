"""Harborview Health Partners — Gold EPO 1000, plan years 2025 and 2026.

Style: an employer plan booklet with "Part A — ..." headings and long-form
dates. Nuances: EPO (no out-of-network coverage except emergencies and
urgent care while travelling); embedded family deductible; therapy limits
per condition; "prior approval" wording; bariatric surgery excluded. The
2025 booklet differs in amounts, for two-plan and outdated-document cases.
"""

YEARS = {
    2025: {"deductible": ("$750", "$1,500"), "oop": ("$4,000", "$8,000"), "specialist": "$40",
           "er": "$200", "pt": "20"},
    2026: {"deductible": ("$1,000", "$2,000"), "oop": ("$4,500", "$9,000"), "specialist": "$45",
           "er": "$250", "pt": "25"},
}


def _policy(year: int) -> dict:
    y = YEARS[year]
    return {
        "filename": f"harborview_gold_epo_{year}.pdf",
        "title_lines": [
            ("Harborview Health Partners", "title"),
            (f"Gold EPO 1000 — Member Benefit Booklet {year}", "subtitle"),
            (f"Group Number: HHP-EPO-1000-{year}", "body"),
            (f"Plan year: January 1, {year} through December 31, {year}", "body"),
            ("Harborview Health Partners is a fictional insurer used for testing. This booklet "
             "does not describe a real policy.", "body"),
        ],
        "sections": [
            ("Part A — Your Costs", [
                f"Annual deductible: {y['deductible'][0]} per person, {y['deductible'][1]} per "
                "family. The deductible is embedded: once one person meets the individual "
                "deductible, the plan begins paying for that person even if the family "
                "deductible has not been met.",
                f"Out-of-pocket maximum: {y['oop'][0]} per person, {y['oop'][1]} per family.",
                "Coinsurance after the deductible: you pay 10%.",
                "",
                {"table": [
                    ["Service", "You pay"],
                    ["Primary care office visit", "$20 copay, deductible waived"],
                    ["Specialist office visit", f"{y['specialist']} copay, deductible waived"],
                    ["Telehealth visit", "$0"],
                    ["Urgent care center", "$50 copay"],
                    ["Emergency room", f"{y['er']} copay, waived if admitted"],
                    ["Mental health office visit", "$20 copay, deductible waived"],
                ]},
            ]),
            ("Part B — Using the Network", [
                "This is an exclusive provider organization (EPO) plan. Services from providers "
                "outside the Harborview network are not covered, except emergency care and "
                "urgent care when you are traveling outside the service area.",
                "You do not need a referral to see a network specialist.",
            ]),
            ("Part C — Prior Approval", [
                "Prior approval from Harborview is required before you receive:",
                "• Inpatient hospital admissions (emergency admissions must be reported within "
                "48 hours)",
                "• MRI, CT and PET scans",
                "• Sleep studies",
                "• Durable medical equipment costing more than $500",
                "• Home health care",
                "Harborview decides standard prior approval requests within 15 calendar days "
                "and urgent requests within 72 hours. Without prior approval, the claim may be "
                "denied.",
            ]),
            ("Part D — What Is Covered", [
                "Preventive care, including annual physicals and immunizations, is covered at no "
                "cost.",
                f"Physical, occupational and speech therapy: up to {y['pt']} visits per condition "
                "per calendar year.",
                "Chiropractic care: up to 15 visits per calendar year.",
                "Prescription drugs: Tier 1 $10, Tier 2 $35, Tier 3 $70, specialty drugs 30% up "
                "to $250 per fill.",
                "Maternity care: prenatal visits covered at no cost; hospital delivery at 10% "
                "after the deductible.",
            ]),
            ("Part E — What Is Not Covered", [
                "• Cosmetic surgery and procedures",
                "• Bariatric (weight-loss) surgery",
                "• In vitro fertilization",
                "• Custodial care",
                "• Hearing aids for adults",
                "• Services from out-of-network providers, except as described in Part B",
            ]),
            ("Part F — Appeals", [
                "You may appeal a denied claim or prior approval decision within 180 days. "
                "Urgent appeals are decided within 72 hours.",
            ]),
        ],
    }


POLICY_2025 = _policy(2025)
POLICY_2026 = _policy(2026)
