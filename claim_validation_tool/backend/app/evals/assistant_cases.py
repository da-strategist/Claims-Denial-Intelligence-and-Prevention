"""Evaluation set for the clarification assistant, written against the reference tables in
Data/raw_data/. Each case is a billing question a specialist might ask, with:

- expected_sources: reference IDs the answer must rest on (retrieval recall, and the answer
  should cite them)
- answer_terms: facts a correct answer states (case-insensitive substrings)
- unanswerable: the tables don't hold the answer, so a correct reply says so instead of guessing
"""

from dataclasses import dataclass, field

from app.models import ClaimFacts, ClarificationTopic

MN = ClarificationTopic.MEDICAL_NECESSITY
NCCI = ClarificationTopic.NCCI_MODIFIERS
PA = ClarificationTopic.PAYER_PRIOR_AUTH
APPEAL = ClarificationTopic.APPEAL

PAYERS = {
    "PAY001": ("Medicare FFS", "Medicare"),
    "PAY002": ("Blue Cross NC", "Commercial"),
    "PAY004": ("UnitedHealthcare MA", "Medicare Advantage"),
    "PAY006": ("Aetna", "Commercial"),
}


def claim(
    lines: list[tuple[str, str, str, int]],
    payer_id: str = "PAY001",
    denials: list[tuple[str, str, str]] = (),
    **changes,
) -> ClaimFacts:
    """Claim facts from (cpt, category, icd10, units) lines and (carc, rarc, category) denials."""
    name, payer_type = PAYERS[payer_id]
    diagnoses = list(dict.fromkeys(icd10 for _, _, icd10, _ in lines))
    fields = dict(
        claim_type="Professional",
        place_of_service="22",
        service_month="2025-06",
        status="Denied" if denials else "Draft",
        payer_id=payer_id,
        payer_name=name,
        payer_type=payer_type,
        primary_icd10=diagnoses[0],
        additional_icd10=diagnoses[1:],
        lines=[
            {
                "cpt_code": cpt,
                "cpt_category": category,
                "modifier": None,
                "units": units,
                "charge_amount": 500.0,
                "icd10_pointer": icd10,
            }
            for cpt, category, icd10, units in lines
        ],
        total_charge=500.0 * len(lines),
        total_paid=0.0,
        days_in_ar=30 if denials else 0,
        pa_required=False,
        pa_obtained=False,
        has_pa_number=False,
        denials=[
            {
                "carc_code": carc,
                "rarc_code": rarc,
                "root_cause_category": category,
                "denial_amount": 500.0,
                "is_preventable": True,
            }
            for carc, rarc, category in denials
        ],
    )
    return ClaimFacts(**{**fields, **changes})


@dataclass(frozen=True)
class EvalCase:
    id: str
    question: str
    topic: ClarificationTopic | None = None
    facts: ClaimFacts | None = None
    expected_sources: tuple[str, ...] = ()
    answer_terms: tuple[str, ...] = ()
    unanswerable: bool = False
    notes: str = field(default="", compare=False)


CASES = [
    # --- Medical necessity -------------------------------------------------------------
    EvalCase(
        "mn-cath-covered",
        "Does the diagnosis support medical necessity for this cardiac cath?",
        MN,
        claim([("93458", "Cardiology", "I25.10", 1)]),
        expected_sources=("NCD-20.9",),
        answer_terms=("I25.10", "covered"),
    ),
    EvalCase(
        "mn-mri-not-covered",
        "Will Medicare cover this brain MRI for this diagnosis?",
        MN,
        claim([("70553", "Radiology", "M54.5", 1)]),
        expected_sources=("LCD-L35056",),
        answer_terms=("M54.5", "not"),
        notes="M54.5 (low back pain) isn't on the MRI brain covered list",
    ),
    EvalCase(
        "mn-tka-documentation",
        "What documentation do we need for this knee replacement?",
        MN,
        claim([("27447", "Orthopedics", "M17.11", 1)], payer_id="PAY004"),
        expected_sources=("LCD-L33789",),
        answer_terms=("conservative", "x-ray"),
    ),
    EvalCase(
        "mn-egd-question-only",
        "When is an upper GI endoscopy medically necessary for GERD?",
        MN,
        expected_sources=("LCD-L33631",),
        answer_terms=("PPI", "8"),
    ),
    EvalCase(
        "mn-screening-colonoscopy-interval",
        "How often can we bill a screening colonoscopy G0121 for an average-risk patient?",
        MN,
        expected_sources=("NCD-210.3",),
        answer_terms=("10 years",),
    ),
    # --- NCCI / modifiers / MUE ----------------------------------------------------------
    EvalCase(
        "ncci-cath-ecg-modifier",
        "Can the ECG be billed with the heart cath, and with which modifier?",
        NCCI,
        claim([("93458", "Cardiology", "I25.10", 1), ("93000", "Cardiology", "I25.10", 1)]),
        expected_sources=("PTP0010",),
        answer_terms=("59", "separate"),
    ),
    EvalCase(
        "ncci-office-visits-not-allowed",
        "Can we bill both office visits on this claim?",
        NCCI,
        claim([("99215", "E&M", "I10", 1), ("99214", "E&M", "I10", 1)], payer_id="PAY002"),
        expected_sources=("PTP0004",),
        answer_terms=("99214", "not"),
    ),
    EvalCase(
        "ncci-lab-panels-question-only",
        "Can CPT 80053 and 80048 be billed together on the same day?",
        NCCI,
        expected_sources=("PTP0016",),
        answer_terms=("comprehensive", "not"),
    ),
    EvalCase(
        "ncci-psychotherapy",
        "Is it OK to bill 90837 and 90834 for the same patient on one day?",
        NCCI,
        expected_sources=("PTP0037", "MUE0035"),
        answer_terms=("not",),
    ),
    EvalCase(
        "mue-therapy-units",
        "Why might the therapeutic exercise units be cut back?",
        NCCI,
        claim([("97110", "Rehab", "M54.5", 6)]),
        expected_sources=("MUE0040",),
        answer_terms=("4", "units"),
    ),
    # --- Payer prior authorization and contracts ------------------------------------------
    EvalCase(
        "pa-uhc-ma-knee",
        "Does UnitedHealthcare MA require prior authorization for this knee replacement?",
        PA,
        claim([("27447", "Orthopedics", "M17.11", 1)], payer_id="PAY004", pa_required=True),
        expected_sources=("PAY004",),
        answer_terms=("prior authorization",),
        unanswerable=True,
        notes="The payer profile has a strictness score but no list of services needing PA",
    ),
    EvalCase(
        "pa-aetna-surgery-rate",
        "What does Aetna reimburse for surgery under our contract?",
        PA,
        expected_sources=("CON0076",),
        answer_terms=("102.5%",),
    ),
    EvalCase(
        "pa-uhc-ortho-contract",
        "What will the payer pay on this claim under our contract?",
        PA,
        claim([("27447", "Orthopedics", "M17.11", 1)], payer_id="PAY004"),
        expected_sources=("CON0041",),
        answer_terms=("91.4%",),
    ),
    # --- Appeals ----------------------------------------------------------------------------
    EvalCase(
        "appeal-missing-auth",
        "Draft appeal wording for this denial.",
        APPEAL,
        claim(
            [("27447", "Orthopedics", "M17.11", 1)],
            payer_id="PAY002",
            denials=[("197", "N362", "Prior Authorization")],
        ),
        expected_sources=("197", "N362"),
        answer_terms=("authorization",),
    ),
    EvalCase(
        "appeal-medical-necessity",
        "How should we appeal this denial?",
        APPEAL,
        claim(
            [("74177", "Radiology", "R10.9", 1)],
            denials=[("50", "M79", "Medical Necessity")],
        ),
        expected_sources=("50", "M79", "LCD-L35081"),
        answer_terms=("R10.9", "medical necessity"),
    ),
    EvalCase(
        "carc-group-question-only",
        "Who owes the balance on a CARC 2 adjustment?",
        APPEAL,
        expected_sources=("2",),
        answer_terms=("patient",),
    ),
    # --- Outside the knowledge base -----------------------------------------------------------
    EvalCase(
        "timely-filing-limit",
        "What is Aetna's timely filing limit?",
        PA,
        expected_sources=("PAY006",),
        unanswerable=True,
        notes="No table records filing limits; the answer must not invent one",
    ),
]
