"""Validation questions and expected answers, written from the plan text in
synthetic_data/validation/plans/ before the app was run on them.

Each question:
    id, docs        documents in scope (one, or several for a person with several plans)
    question        as a member or staff member would ask it
    expected        the correct answer in words (for the reviewer)
    phrases         verbatim text from the document that answers it; the answer must
                    contain any one of them ("all" questions: every one of them)
    all             True: every phrase is needed (multi-plan answers name each plan)
    sections        where the answer lives (any substring, case-insensitive)
    category        lookup · nuance · abstain · multi_plan · scanned
    note            what makes it tricky (for the reviewer)
    forbidden       amounts that must not appear (the other plan's), for named-plan questions
    differs         multi-plan: a difference between plans that should be flagged
    same            multi-plan: the plans agree; nothing should be flagged
Abstain questions have no phrases: the documents don't answer them, and the app
should say so instead of quoting something unrelated.
"""

CEDAR = "cedar_valley_silver_3500_2026.pdf"
HARBOR_25 = "harborview_gold_epo_2025.pdf"
HARBOR_26 = "harborview_gold_epo_2026.pdf"
PINE = "pinecrest_senior_care_hmo_2026.pdf"
LAKE = "lakeshore_student_health_2025.pdf"
MERID = "meridian_catastrophic_2026.pdf"
MERID_SCAN = "meridian_catastrophic_2026_scanned.pdf"

METADATA = {
    CEDAR: {"insurer_name": "Cedar Valley Health Plan", "plan_name": "Cedar Silver 3500",
            "plan_id": "CVH-SLV-3500-26", "effective_date": "2026-01-01", "expiration_date": "2026-12-31"},
    HARBOR_25: {"insurer_name": "Harborview Health Partners", "plan_name": "Gold EPO 1000",
                "plan_id": "HHP-EPO-1000-2025", "effective_date": "2025-01-01", "expiration_date": "2025-12-31"},
    HARBOR_26: {"insurer_name": "Harborview Health Partners", "plan_name": "Gold EPO 1000",
                "plan_id": "HHP-EPO-1000-2026", "effective_date": "2026-01-01", "expiration_date": "2026-12-31"},
    PINE: {"insurer_name": "Pinecrest Health", "plan_name": "Pinecrest Senior Care HMO",
           "plan_id": "H9917-004", "effective_date": "2026-01-01", "expiration_date": "2026-12-31"},
    LAKE: {"insurer_name": "Bayfront Life & Health Insurance Company",
           "plan_name": "Student Health Insurance Plan", "plan_id": "BLH-SHIP-2025",
           "effective_date": "2025-08-15", "expiration_date": "2026-08-14"},
    MERID: {"insurer_name": "Meridian Health Cooperative", "plan_name": "Catastrophic Shield 10150",
            "plan_id": "MHC-CAT-10150", "effective_date": "2026-01-01", "expiration_date": "2026-12-31"},
}
METADATA[MERID_SCAN] = METADATA[MERID]

METADATA_NOTES = {
    LAKE: "Insurer: the underwriter (Bayfront) rather than the university. Plan name could "
          "also be read as 'Lakeshore University Student Health Insurance Plan'.",
    PINE: "Plan ID: the Medicare contract number.",
}


def _q(id, docs, question, expected, phrases=(), sections=(), category="lookup", note="", **extra):
    return {"id": id, "docs": list(docs), "question": question, "expected": expected,
            "phrases": list(phrases), "sections": list(sections), "category": category,
            "note": note, **extra}


QUESTIONS = [
    # ── Cedar Valley Silver 3500: SBC tables ───────────────────────────
    _q("CV-01", [CEDAR], "What is the deductible?", "$3,500 individual / $7,000 family.",
       ["$3,500 individual"], ["Important Questions"]),
    _q("CV-02", [CEDAR], "If only my child has medical bills, does the plan start paying once "
       "my child reaches $3,500?",
       "No. The deductible is non-embedded: the whole $7,000 family deductible must be met first.",
       ["Non-embedded"], ["Important Questions"], "nuance", "Non-embedded family deductible."),
    _q("CV-03", [CEDAR], "Do I have to meet the deductible before a primary care visit?",
       "No. Primary care is a $30 copay per visit and the deductible does not apply.",
       ["$30 copay/visit"], ["Common Medical Event", "Important Questions"], "nuance",
       "Copay before the deductible."),
    _q("CV-04", [CEDAR], "How much is a specialist visit?",
       "$75 copay per visit after the deductible; a referral is required.",
       ["$75 copay"], ["Common Medical Event"], "nuance",
       "Unlike primary care, the specialist copay applies only after the deductible."),
    _q("CV-05", [CEDAR], "Do I need a referral to see a specialist?",
       "Yes, a written referral from your primary care provider.",
       ["written referral"], ["Important Questions"]),
    _q("CV-06", [CEDAR], "Does an MRI need preauthorization?",
       "Yes. 20% coinsurance in network; without preauthorization benefits are reduced by 50% "
       "of the allowed amount, up to $1,000.",
       ["reduced by 50%"], ["Common Medical Event"]),
    _q("CV-07", [CEDAR], "Does an MRI need prior authorization?",
       "Yes (the plan calls it preauthorization); without it benefits are reduced by 50%, up "
       "to $1,000.",
       ["reduced by 50%"], ["Common Medical Event"], "nuance",
       "The plan says 'preauthorization', the question says 'prior authorization'."),
    _q("CV-08", [CEDAR], "What is the out-of-pocket limit?", "$8,000 individual / $16,000 family.",
       ["$8,000 individual"], ["Important Questions"]),
    _q("CV-09", [CEDAR], "Is out-of-network care covered?",
       "Yes, at 50% coinsurance after the deductible.",
       ["50% coinsurance after the deductible"], ["Important Questions"]),
    _q("CV-10", [CEDAR], "How much is an emergency room visit?",
       "$400 copay per visit, then 20% coinsurance; the copay is waived if you are admitted.",
       ["$400 copay"], ["Common Medical Event"]),
    _q("CV-11", [CEDAR], "How many physical therapy visits are covered?",
       "20 visits per year for physical, occupational and speech therapy combined.",
       ["20 visits per year"], ["Common Medical Event"], "nuance",
       "The limit is shared across three therapies."),
    _q("CV-12", [CEDAR], "Is acupuncture covered?", "No, it is excluded.",
       ["Acupuncture"], ["Excluded Services"]),
    _q("CV-13", [CEDAR], "Are children's glasses covered?",
       "No. A children's eye exam is covered once a year, but glasses are not.",
       ["Children's glasses"], ["Common Medical Event"], "nuance",
       "Exam covered, glasses not."),
    _q("CV-14", [CEDAR], "How many chiropractic visits are covered?", "12 visits per year.",
       ["12 visits per year"], ["Other Covered Services", "Excluded Services"]),
    _q("CV-15", [CEDAR], "How long does a preauthorization decision take?",
       "15 days for standard requests, 72 hours for urgent requests.",
       ["within 15 days"], ["Appeals", "Your Rights"]),
    _q("CV-16", [CEDAR], "Do penalties for missing preauthorization count toward the "
       "out-of-pocket limit?",
       "No, they are not included in the out-of-pocket limit.",
       ["penalties for failure to obtain"], ["Important Questions"], "nuance"),
    _q("CV-17", [CEDAR], "What is my monthly premium?",
       "Not stated in this document.", category="abstain"),
    _q("CV-18", [CEDAR], "Does the plan pay for gym memberships?",
       "Not stated in this document.", category="abstain"),
    _q("CV-19", [CEDAR], "Is LASIK eye surgery covered?",
       "Not stated in this document.", category="abstain",
       note="Cosmetic surgery is excluded, but LASIK is not mentioned."),

    # ── Harborview Gold EPO 1000 (2026 booklet) ────────────────────────
    _q("HV-01", [HARBOR_26], "What is the deductible?", "$1,000 per person, $2,000 per family.",
       ["$1,000 per person"], ["Your Costs"]),
    _q("HV-02", [HARBOR_26], "Once one family member meets their own deductible, does the plan "
       "start paying for them?",
       "Yes. The deductible is embedded.", ["embedded"], ["Your Costs"], "nuance",
       "Embedded deductible (the opposite of Cedar Valley)."),
    _q("HV-03", [HARBOR_26], "How much is a specialist visit?",
       "$45 copay, deductible waived.", ["$45 copay"], ["Your Costs"]),
    _q("HV-04", [HARBOR_26], "Is out-of-network care covered?",
       "No. It's an EPO: out-of-network providers are not covered except emergency care and "
       "urgent care when traveling outside the service area.",
       ["are not covered, except emergency care"], ["Using the Network"], "nuance", "EPO rules."),
    _q("HV-05", [HARBOR_26], "Do I need a referral to see a specialist?",
       "No referral is needed for a network specialist.", ["do not need a referral"],
       ["Using the Network"]),
    _q("HV-06", [HARBOR_26], "Does an MRI need prior authorization?",
       "Yes. The plan calls it prior approval.", ["MRI, CT and PET scans"], ["Prior Approval"],
       "nuance", "The plan says 'prior approval'."),
    _q("HV-07", [HARBOR_26], "How long does Harborview take to decide a prior approval request?",
       "15 calendar days for standard requests, 72 hours for urgent requests.",
       ["15 calendar days"], ["Prior Approval"]),
    _q("HV-08", [HARBOR_26], "How many physical therapy visits can I get?",
       "Up to 25 visits per condition per calendar year.", ["25 visits per condition"],
       ["What Is Covered"], "nuance", "Limit per condition, not per year overall."),
    _q("HV-09", [HARBOR_26], "Is bariatric surgery covered?", "No, it is excluded.",
       ["Bariatric (weight-loss) surgery"], ["What Is Not Covered"]),
    _q("HV-10", [HARBOR_26], "How much is the emergency room?",
       "$250 copay, waived if admitted.", ["$250 copay"], ["Your Costs"]),
    _q("HV-11", [HARBOR_26], "What do specialty drugs cost?", "30% up to $250 per fill.",
       ["30% up to $250 per fill"], ["What Is Covered"]),
    _q("HV-12", [HARBOR_26], "Can I get a sleep study without approval?",
       "No, sleep studies need prior approval.", ["Sleep studies"], ["Prior Approval"]),
    _q("HV-13", [HARBOR_26], "What is the out-of-pocket maximum?",
       "$4,500 per person, $9,000 per family.", ["$4,500 per person"], ["Your Costs"]),
    _q("HV-14", [HARBOR_26], "Does the plan cover travel vaccines?",
       "Not stated in this document.", category="abstain"),
    _q("HV-15", [HARBOR_26], "What is the copay for an ambulance?",
       "Not stated in this document.", category="abstain"),

    # ── Pinecrest Senior Care HMO (Medicare Advantage) ─────────────────
    _q("PC-01", [PINE], "What is the deductible?",
       "There is no medical deductible (maximum out-of-pocket $5,900); the drug deductible is "
       "$250 for Tiers 3–5.",
       ["no medical deductible"], ["Medical Benefits Chart"], "nuance",
       "No medical deductible, but a separate drug deductible."),
    _q("PC-02", [PINE], "What is the maximum out-of-pocket amount?", "$5,900 per year in network.",
       ["$5,900 per year"], ["Medical Benefits Chart"]),
    _q("PC-03", [PINE], "How much does a specialist visit cost?",
       "$35 copay; a referral from your PCP is required.", ["$35 copay"],
       ["Medical Benefits Chart"]),
    _q("PC-04", [PINE], "What would a 7-day hospital stay cost?",
       "$325 per day for days 1–5 ($1,625), then $0 for days 6–7; prior authorization required.",
       ["$325 copay per day"], ["Medical Benefits Chart"], "nuance", "Per-day copay tiers."),
    _q("PC-05", [PINE], "Does an MRI need prior authorization?",
       "Yes; $150 copay.", ["$150 copay"], ["Medical Benefits Chart"]),
    _q("PC-06", [PINE], "Do I need approval in advance for outpatient surgery?",
       "Yes, prior authorization is required; $250 copay.", ["$250 copay"],
       ["Medical Benefits Chart"], "nuance", "'Approval in advance' wording."),
    _q("PC-07", [PINE], "Does the drug deductible apply to generic drugs?",
       "No. It applies to Tiers 3, 4 and 5 only; Tier 1 and Tier 2 are not subject to it.",
       ["Tier 1 and Tier 2 drugs are not subject to the deductible"], ["Part D"], "nuance"),
    _q("PC-08", [PINE], "Are hearing aids covered?",
       "Yes: $499 or $799 per aid, up to two aids per year.", ["$499 or $799 per aid"],
       ["Extra benefits"]),
    _q("PC-09", [PINE], "How much dental coverage is there?",
       "Two cleanings and exams per year at $0; comprehensive dental up to a $1,500 annual "
       "maximum.", ["$1,500 annual maximum"], ["Extra benefits"]),
    _q("PC-10", [PINE], "Is routine foot care covered?",
       "Not covered, except for members with diabetes or certain other conditions.",
       ["Routine foot care"], ["not covered", "exclusions"], "nuance", "Exception inside an exclusion."),
    _q("PC-11", [PINE], "Do I still pay my Part B premium?", "Yes.",
       ["continue to pay your Medicare Part B premium"], ["Getting started"]),
    _q("PC-12", [PINE], "How long do I have to file an appeal?", "65 calendar days.",
       ["within 65 calendar days"], ["problem or complaint"]),
    _q("PC-13", [PINE], "What do skilled nursing days 21 to 100 cost?", "$203 per day.",
       ["$203 per day"], ["Medical Benefits Chart"]),
    _q("PC-14", [PINE], "How much is a Tier 2 drug?", "$8 for a 30-day supply at a preferred pharmacy.",
       ["Tier 2 (generic)"], ["Part D"]),
    _q("PC-15", [PINE], "Does the plan cover acupuncture?",
       "Not stated in this document.", category="abstain"),
    _q("PC-16", [PINE], "Is there a monthly allowance for over-the-counter items?",
       "Not stated in this document.", category="abstain"),

    # ── Lakeshore Student Health Insurance Plan (two columns, footnotes) ─
    _q("LS-01", [LAKE], "What is the deductible?", "$250 in network, $500 out of network, per policy year.",
       ["$250 per policy year"], ["What You Pay"]),
    _q("LS-02", [LAKE], "Do I pay the deductible at the Student Health Center?",
       "No. Visits there are no charge and the deductible does not apply.",
       ["deductible does not apply", "deductible is waived"], ["What You Pay"], "nuance",
       "Stated in a footnote as well."),
    _q("LS-03", [LAKE], "How many free counseling sessions do I get?",
       "The first 12 sessions per policy year at the University Counseling Center, then $20 each.",
       ["first 12 sessions"], ["Mental Health"]),
    _q("LS-04", [LAKE], "Do sessions with an off-campus therapist count toward the free sessions?",
       "No.", ["do not count toward the 12 free"], ["Mental Health"], "nuance",
       "Only in a footnote."),
    _q("LS-05", [LAKE], "Does an MRI need prior authorization?",
       "Yes (pre-certification); benefits are reduced by 20% without it.",
       ["reduced by 20%"], ["Pre-Certification"], "nuance", "'Pre-certification' wording."),
    _q("LS-06", [LAKE], "I was injured playing on the university soccer team. Is that covered?",
       "No. Injuries from intercollegiate sports are excluded.", ["intercollegiate"],
       ["Exclusions"], "nuance", "The question doesn't use the word 'intercollegiate'."),
    _q("LS-07", [LAKE], "Are dental cleanings covered?",
       "No. Only injury to sound natural teeth is covered, up to $500 per accident.",
       ["Routine dental care, cleanings"], ["Covered Benefits"], "nuance", "Only in a footnote."),
    _q("LS-08", [LAKE], "How many physical therapy visits are covered?",
       "Up to 30 visits per policy year at 20% coinsurance.", ["up to 30 visits per policy year"],
       ["Covered Benefits"]),
    _q("LS-09", [LAKE], "When does the policy year end?", "August 14, 2026.",
       ["August 14, 2026"], ["Lakeshore", "Student Health"]),
    _q("LS-10", [LAKE], "How long do I have to file a claim?", "90 days from the date of service.",
       ["within 90 days"], ["Claims and Appeals"]),
    _q("LS-11", [LAKE], "How much is the emergency room?",
       "$150 copay, then coinsurance; waived if admitted.", ["$150 copay"], ["What You Pay"]),
    _q("LS-12", [LAKE], "Can I add my spouse to the plan?",
       "Yes; spouses and children under 26 may be added.", ["Spouses and children under 26"],
       ["Who Is Covered"]),
    _q("LS-13", [LAKE], "Does the plan cover me while studying abroad?",
       "Not stated in this document.", category="abstain"),
    _q("LS-14", [LAKE], "How much does the plan cost per semester?",
       "Not stated in this document.", category="abstain"),

    # ── Meridian Catastrophic Shield 10150 (text PDF) ──────────────────
    _q("MD-01", [MERID], "What is the deductible?",
       "$10,150 per person, the same as the out-of-pocket maximum.", ["$10,150 per person"],
       ["What you pay"], "nuance", "Deductible equals the out-of-pocket maximum."),
    _q("MD-02", [MERID], "Are any doctor visits covered before the deductible?",
       "Yes: three primary care visits per year at a $40 copay, plus preventive care at no cost.",
       ["three primary care visits per year"], ["What you pay"], "nuance"),
    _q("MD-03", [MERID], "Is a specialist visit covered before the deductible?",
       "No; you pay in full until the deductible is met.",
       ["paid in full by you until the deductible is met"], ["What you pay"]),
    _q("MD-04", [MERID], "Does a planned hospital stay need prior authorization?",
       "Yes; the plan calls it pre-service review.", ["Pre-service review is required"],
       ["Pre-service review"], "nuance", "'Pre-service review': wording the app has never seen."),
    _q("MD-05", [MERID], "Is bariatric surgery covered?",
       "It needs pre-service review; surgery is covered after the deductible.",
       ["bariatric surgery"], ["Pre-service review"], "nuance",
       "Coverage is implied (surgery covered) rather than stated for bariatric surgery."),
    _q("MD-06", [MERID], "Who can enroll in this plan?",
       "People under 30, or of any age with a hardship or affordability exemption.",
       ["under age 30"], ["Who can enroll"]),
    _q("MD-07", [MERID], "Are hearing aids covered?", "No.", ["hearing aids"], ["Not covered"]),
    _q("MD-08", [MERID], "How many rehabilitation visits are covered?", "20 visits per year.",
       ["limited to 20 visits per year"], ["Covered services"]),
    _q("MD-09", [MERID], "Does the plan come with a health savings account?",
       "Not stated in this document.", category="abstain"),
    _q("MD-10", [MERID], "Is chiropractic care covered?",
       "Not stated in this document.", category="abstain"),

    # ── Meridian, scanned copy (read by OCR) ───────────────────────────
    _q("MS-01", [MERID_SCAN], "What is the deductible?", "$10,150 per person.",
       ["$10,150 per person"], ["What you pay"], "scanned"),
    _q("MS-02", [MERID_SCAN], "Are any doctor visits covered before the deductible?",
       "Three primary care visits per year at a $40 copay.",
       ["three primary care visits per year"], ["What you pay"], "scanned"),
    _q("MS-03", [MERID_SCAN], "Does a planned hospital stay need prior authorization?",
       "Yes, pre-service review.", ["Pre-service review is required"], ["Pre-service review"],
       "scanned"),
    _q("MS-04", [MERID_SCAN], "How many rehabilitation visits are covered?", "20 visits per year.",
       ["limited to 20 visits per year"], ["Covered services"], "scanned"),
    _q("MS-05", [MERID_SCAN], "Are hearing aids covered?", "No.", ["hearing aids"],
       ["Not covered"], "scanned"),
    _q("MS-06", [MERID_SCAN], "Who can enroll in this plan?", "Under 30, or with an exemption.",
       ["under age 30"], ["Who can enroll"], "scanned"),

    # ── People with several plans ──────────────────────────────────────
    _q("MP-01", [HARBOR_25, HARBOR_26], "What is my deductible?",
       "Both booklets shown separately: $750 per person (2025) and $1,000 per person (2026); "
       "the difference is flagged.",
       ["$750 per person", "$1,000 per person"], category="multi_plan", all=True,
       differs="Deductible", note="Same plan, two plan years: one is out of date."),
    _q("MP-02", [HARBOR_25, HARBOR_26], "How much is a specialist visit?",
       "$40 (2025) and $45 (2026), shown separately and flagged.",
       ["$40 copay", "$45 copay"], category="multi_plan", all=True, differs="Specialist"),
    _q("MP-03", [HARBOR_25, HARBOR_26], "What is the deductible in the 2026 booklet?",
       "$1,000 per person (2026 only).", ["$1,000 per person"], category="multi_plan",
       forbidden=["$750"], note="Both booklets have the same plan name; only the year differs."),
    _q("MP-04", [HARBOR_25, HARBOR_26], "Does an MRI need prior approval?",
       "Yes, in both years.", ["MRI, CT and PET scans"], category="multi_plan", same=True),
    _q("MP-05", [CEDAR, PINE], "What is my deductible?",
       "Cedar Silver 3500: $3,500 individual / $7,000 family. Pinecrest: no medical "
       "deductible. Shown separately.",
       ["$3,500 individual", "no medical deductible"], category="multi_plan", all=True,
       differs="Deductible"),
    _q("MP-06", [CEDAR, PINE], "How much is a specialist visit under Cedar Silver 3500?",
       "$75 copay after the deductible (Cedar only).", ["$75 copay"], category="multi_plan",
       forbidden=["$35"]),
    _q("MP-07", [CEDAR, PINE], "Do I need a referral to see a specialist?",
       "Yes under both plans.", ["written referral", "referral from your PCP required"],
       category="multi_plan", all=True),
    _q("MP-08", [LAKE, MERID], "What is the out-of-pocket maximum?",
       "Lakeshore: $6,350 per insured person; Meridian: $10,150. Flagged as different.",
       ["$6,350", "$10,150"], category="multi_plan", all=True, differs="Out-of-pocket"),
    _q("MP-09", [LAKE, MERID], "Is physical therapy limited?",
       "Lakeshore: up to 30 visits per policy year. Meridian: rehabilitation limited to 20 "
       "visits per year.", ["up to 30 visits per policy year", "limited to 20 visits per year"],
       category="multi_plan", all=True),
    _q("MP-10", [LAKE, MERID], "How much is the emergency room under Catastrophic Shield 10150?",
       "Covered after the deductible; you pay in full until the $10,150 deductible is met "
       "(Meridian only).", ["Emergency care"], category="multi_plan", forbidden=["$150"]),
]
