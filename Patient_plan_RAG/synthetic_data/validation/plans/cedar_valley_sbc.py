"""Cedar Valley Health Plan — Cedar Silver 3500 (2026).

Style: the standard "Summary of Benefits and Coverage" layout — an
"Important Questions" table and a "Common Medical Event" table — with
"Coverage Period" dates. Nuances: non-embedded family deductible; primary
care copay before the deductible; specialist copay after it; referrals
required; "preauthorization" with a benefit reduction if skipped.
"""

POLICY = {
    "filename": "cedar_valley_silver_3500_2026.pdf",
    "title_lines": [
        ("Summary of Benefits and Coverage: What this Plan Covers &amp; What You Pay for Covered Services", "subtitle"),
        ("Cedar Valley Health Plan: Cedar Silver 3500", "title"),
        ("Coverage Period: 01/01/2026 - 12/31/2026", "body"),
        ("Coverage for: Individual + Family | Plan Type: HMO | Plan ID: CVH-SLV-3500-26", "body"),
        ("Cedar Valley Health Plan is a fictional insurer used for testing. This document does not "
         "describe a real policy.", "body"),
    ],
    "sections": [
        ("Important Questions", [
            {"table": [
                ["Important Questions", "Answers", "Why This Matters"],
                ["What is the overall deductible?",
                 "$3,500 individual / $7,000 family. Non-embedded: the whole family deductible must "
                 "be met before the plan pays for any family member.",
                 "Generally, you must pay all of the costs from providers up to the deductible "
                 "amount before this plan begins to pay."],
                ["Are there services covered before you meet your deductible?",
                 "Yes. Preventive care and primary care visits are covered before you meet your "
                 "deductible.",
                 "This plan covers some items and services even if you haven't yet met the "
                 "deductible amount."],
                ["What is the out-of-pocket limit for this plan?",
                 "$8,000 individual / $16,000 family.",
                 "The out-of-pocket limit is the most you could pay in a year for covered services."],
                ["What is not included in the out-of-pocket limit?",
                 "Premiums, balance-billed charges, penalties for failure to obtain "
                 "preauthorization, and health care this plan doesn't cover.",
                 "Even though you pay these expenses, they don't count toward the out-of-pocket "
                 "limit."],
                ["Will you pay less if you use a network provider?",
                 "Yes. This plan uses the Cedar Valley Select network. Out-of-network care is "
                 "covered at 50% coinsurance after the deductible.",
                 "You pay the least if you use a provider in the plan's network."],
                ["Do you need a referral to see a specialist?",
                 "Yes. You need a written referral from your primary care provider.",
                 "This plan will pay some or all of the costs to see a specialist for covered "
                 "services, but only if you have a referral before you see the specialist."],
            ]},
        ]),
        ("Common Medical Events", [
            {"table": [
                ["Common Medical Event", "Services You May Need", "In-Network (You will pay)",
                 "Out-of-Network (You will pay)", "Limitations, Exceptions, &amp; Other Important Information"],
                ["If you visit a health care provider's office or clinic", "Primary care visit",
                 "$30 copay/visit; deductible does not apply", "50% coinsurance", "Includes telehealth visits."],
                ["", "Specialist visit", "$75 copay/visit after deductible", "50% coinsurance",
                 "Referral required."],
                ["", "Preventive care/screening/immunization", "No charge", "Not covered",
                 "You may have to pay for services that aren't preventive."],
                ["If you have a test", "Diagnostic test (x-ray, blood work)", "20% coinsurance",
                 "50% coinsurance", "None"],
                ["", "Imaging (CT/PET scans, MRIs)", "20% coinsurance", "50% coinsurance",
                 "Preauthorization required. If you don't get preauthorization, benefits are "
                 "reduced by 50% of the allowed amount, up to $1,000."],
                ["If you need drugs to treat your illness or condition", "Generic drugs (Tier 1)",
                 "$15 copay (retail); deductible does not apply", "Not covered",
                 "Up to a 30-day supply."],
                ["", "Preferred brand drugs (Tier 2)", "$50 copay after deductible", "Not covered",
                 "Up to a 30-day supply."],
                ["", "Specialty drugs (Tier 4)", "30% coinsurance after deductible", "Not covered",
                 "Preauthorization required. Must use the Cedar Valley specialty pharmacy."],
                ["If you have outpatient surgery", "Facility fee (e.g., ambulatory surgery center)",
                 "20% coinsurance", "50% coinsurance", "Preauthorization required."],
                ["If you need immediate medical attention", "Emergency room care",
                 "$400 copay/visit, then 20% coinsurance", "$400 copay/visit, then 20% coinsurance",
                 "Copay waived if you are admitted."],
                ["", "Urgent care", "$60 copay/visit", "50% coinsurance", "None"],
                ["If you have a hospital stay", "Facility fee (e.g., hospital room)", "20% coinsurance",
                 "50% coinsurance", "Preauthorization required except for emergency admissions."],
                ["If you need mental health or substance use disorder services", "Outpatient services",
                 "$30 copay/visit; deductible does not apply", "50% coinsurance", "None"],
                ["If you need help recovering or have other special health needs", "Rehabilitation services",
                 "20% coinsurance", "50% coinsurance",
                 "Limited to 20 visits per year for physical, occupational and speech therapy combined."],
                ["", "Skilled nursing care", "20% coinsurance", "50% coinsurance",
                 "Limited to 60 days per year. Preauthorization required."],
                ["If your child needs dental or eye care", "Children's eye exam", "No charge",
                 "Not covered", "Limited to one exam per year."],
                ["", "Children's glasses", "Not covered", "Not covered", "None"],
            ]},
        ]),
        ("Excluded Services &amp; Other Covered Services", [
            "Services Your Plan Generally Does NOT Cover (check your policy for more information):",
            "• Acupuncture • Cosmetic surgery • Dental care (adult) • Hearing aids • Infertility "
            "treatment • Long-term care • Routine foot care • Weight loss programs",
            "",
            "Other Covered Services (limitations may apply):",
            "• Bariatric surgery (preauthorization required) • Chiropractic care (limited to 12 "
            "visits per year) • Non-emergency care when traveling outside the U.S.",
        ]),
        ("Your Rights to Continue Coverage and Your Grievance and Appeals Rights", [
            "If you disagree with a decision, you can file an appeal within 180 days of the "
            "notice. Cedar Valley decides standard preauthorization requests within 15 days and "
            "urgent requests within 72 hours.",
        ]),
    ],
}
