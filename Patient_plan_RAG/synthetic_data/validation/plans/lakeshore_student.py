"""Lakeshore University Student Health Insurance Plan, policy year 2025–2026.

Style: a two-column brochure with footnotes, underwritten by a separate
insurer, academic-year dates. Nuances: deductible waived at the Student
Health Center; first 12 counseling sessions free; "pre-certification" with a
penalty; intercollegiate sports injuries excluded; accident-only dental.
"""

POLICY = {
    "filename": "lakeshore_student_health_2025.pdf",
    "columns": 2,
    "title_lines": [
        ("Lakeshore University", "title"),
        ("Student Health Insurance Plan 2025–2026", "subtitle"),
        ("Underwritten by Bayfront Life &amp; Health Insurance Company", "body"),
        ("Policy Number: BLH-SHIP-2025", "body"),
        ("Policy Year: August 15, 2025 to August 14, 2026", "body"),
        ("Bayfront Life &amp; Health and Lakeshore University are fictional, used for testing.", "body"),
    ],
    "sections": [
        ("WHO IS COVERED", [
            "All students enrolled in six or more credit hours are covered unless they waive the "
            "plan with proof of other insurance. Spouses and children under 26 may be added as "
            "dependents.",
        ]),
        ("WHAT YOU PAY", [
            "Deductible: $250 per policy year in network; $500 out of network.¹",
            "Coinsurance: 20% in network; 40% out of network.",
            "Out-of-pocket maximum: $6,350 per insured person per policy year in network.",
            "Student Health Center visits: no charge, and the deductible does not apply.",
            "Emergency room: $150 copay, then coinsurance; copay waived if admitted.",
            "Prescription drugs: $10 generic, $40 brand, $75 non-preferred brand.",
            {"note": "¹ The deductible is waived for services received at the Lakeshore Student "
                     "Health Center."},
        ]),
        ("MENTAL HEALTH", [
            "Counseling at the University Counseling Center: no charge for the first 12 sessions "
            "per policy year, then a $20 copay per session.²",
            "Outpatient mental health care from network providers: 20% coinsurance after the "
            "deductible.",
            {"note": "² Sessions with off-campus providers do not count toward the 12 free "
                     "sessions."},
        ]),
        ("PRE-CERTIFICATION", [
            "Pre-certification is required for inpatient admissions, outpatient surgery, and "
            "high-tech imaging (MRI, CT, PET). If pre-certification is not obtained, benefits "
            "are reduced by 20%.",
            "Call Bayfront Care Management at least 5 days before a planned admission.",
        ]),
        ("COVERED BENEFITS", [
            "Preventive care and immunizations: no charge in network.",
            "Physical therapy: 20% coinsurance, up to 30 visits per policy year.",
            "Pediatric vision (dependents under 19): one exam and one pair of glasses per year.",
            "Dental: treatment of injury to sound natural teeth only, up to $500 per accident.³",
            {"note": "³ Routine dental care, cleanings and orthodontics are not covered."},
        ]),
        ("EXCLUSIONS", [
            "The plan does not cover: injuries sustained while participating in intercollegiate "
            "or professional sports; elective cosmetic surgery; routine dental care; eyeglasses "
            "for adults; travel immunizations; treatment covered by workers' compensation.",
        ]),
        ("CLAIMS AND APPEALS", [
            "Claims must be filed within 90 days of the date of service. Appeals must be filed "
            "within 180 days of a denial.",
        ]),
    ],
}
