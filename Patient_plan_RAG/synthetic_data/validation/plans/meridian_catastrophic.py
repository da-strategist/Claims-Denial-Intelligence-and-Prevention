"""Meridian Health Cooperative — Catastrophic Shield 10150 (2026).

Style: plain sentences, numbered sections, ISO dates; also published as a
scanned copy (image-only PDF) to exercise OCR. Nuances: deductible equal to
the out-of-pocket maximum; three primary care visits before the deductible;
eligibility limits; "pre-service review" (yet another name for prior
authorization).
"""

POLICY = {
    "filename": "meridian_catastrophic_2026.pdf",
    "title_lines": [
        ("Meridian Health Cooperative", "title"),
        ("Catastrophic Shield 10150 — Plan Summary", "subtitle"),
        ("Plan code: MHC-CAT-10150", "body"),
        ("Plan effective 2026-01-01 through 2026-12-31", "body"),
        ("Meridian Health Cooperative is a fictional insurer used for testing.", "body"),
    ],
    "sections": [
        ("1. Who can enroll", [
            "This catastrophic plan is available to people under age 30, or to people of any age "
            "with a hardship or affordability exemption.",
        ]),
        ("2. What you pay", [
            "Deductible: $10,150 per person. The deductible is the same as the out-of-pocket "
            "maximum: once you have paid $10,150 for covered services, the plan pays 100% for "
            "the rest of the year.",
            "Before the deductible, the plan covers preventive care at no cost and three primary "
            "care visits per year at a $40 copay each.",
            "All other services, including specialist visits, urgent care and prescriptions, are "
            "paid in full by you until the deductible is met.",
        ]),
        ("3. Pre-service review", [
            "Pre-service review is required for planned hospital stays, organ transplants and "
            "bariatric surgery. Ask your doctor to contact Meridian at least 7 days before the "
            "service. Without pre-service review, Meridian may not pay the claim.",
        ]),
        ("4. Covered services", [
            "Emergency care, hospital stays, surgery, maternity care, mental health care, "
            "prescription drugs and rehabilitation are covered after the deductible. "
            "Rehabilitation therapy is limited to 20 visits per year.",
        ]),
        ("5. Not covered", [
            "Adult dental and vision care, cosmetic procedures, hearing aids, and long-term "
            "care are not covered.",
        ]),
    ],
}
