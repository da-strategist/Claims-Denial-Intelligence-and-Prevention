"""Default validation rule set, loaded into the rule store at startup.

Ported from the prototype's defaultRules.js and recalibrated to the synthetic
dataset (e.g. the billed-amount threshold sits near the 99th percentile of
total_charge, ~$31.6K, rather than the prototype's $50K, which no claim reaches).
"""

from app.models import RuleCreate

# Added in seed version 2: errors from the coding checks on service lines. An organisation
# whose rules were saved before then gets these once (RuleRepository._load)
CODING_RULES: list[RuleCreate] = [
    RuleCreate(
        name="NCCI Procedure-to-Procedure Edit",
        description=(
            "Two procedures on the claim form an NCCI edit: the column 2 code is bundled into "
            "the column 1 code and is denied unless a modifier documents a distinct service"
        ),
        category="Coding",
        severity="error",
        recommended_action=(
            "Remove the bundled line, or add modifier 59 or XE/XS/XP/XU only if the documentation "
            "shows a separate session, site, or practitioner"
        ),
        conditions=[{"field": "ncci_conflict", "operator": "equals", "value": "true"}],
    ),
    RuleCreate(
        name="Units Exceed MUE Limit",
        description="A procedure is billed with more units than its Medically Unlikely Edit allows per day",
        category="Coding",
        severity="error",
        recommended_action="Correct the units to what was performed, within the MUE limit",
        conditions=[{"field": "mue_exceeded", "operator": "equals", "value": "true"}],
    ),
    RuleCreate(
        name="Diagnosis Not Covered (LCD/NCD)",
        description=(
            "A procedure has a coverage policy, and the diagnosis its line points to isn't on "
            "the policy's covered list, so the payer will deny it as not medically necessary"
        ),
        category="Coding",
        severity="error",
        recommended_action=(
            "Check the documentation for a covered diagnosis and code it, or obtain an ABN "
            "before billing a non-covered service"
        ),
        conditions=[{"field": "diagnosis_not_covered", "operator": "equals", "value": "true"}],
    ),
]

# Added in seed version 3: a line whose diagnosis doesn't plausibly fit its procedure
MISMATCH_RULES: list[RuleCreate] = [
    RuleCreate(
        name="Diagnosis Doesn't Match Procedure",
        description=(
            "A specialty procedure points to a diagnosis from an unrelated body system (e.g. an "
            "echocardiogram for anxiety), a common reason for medical necessity denials"
        ),
        category="Coding",
        severity="warning",
        recommended_action=(
            "Point the line at the diagnosis that justifies the procedure, adding it if it's "
            "documented; query the provider if the reason for the service isn't clear"
        ),
        conditions=[{"field": "diagnosis_procedure_mismatch", "operator": "equals", "value": "true"}],
    ),
]

# Rules added to organisations whose saved rules predate each seed version
SEED_ADDITIONS: dict[int, list[RuleCreate]] = {2: CODING_RULES, 3: MISMATCH_RULES}
SEED_VERSION = max(SEED_ADDITIONS)

DEFAULT_RULES: list[RuleCreate] = [
    RuleCreate(
        name="Missing Primary Diagnosis Code",
        description="Claims must have a valid primary ICD-10 diagnosis code to be processed",
        category="Coding",
        severity="error",
        recommended_action="Verify and enter the correct ICD-10 diagnosis code based on clinical documentation",
        conditions=[{"field": "primary_icd10", "operator": "isEmpty"}],
    ),
    RuleCreate(
        name="Missing Prior Authorization",
        description="When prior authorization is required, it must be obtained before claim submission",
        category="Authorization",
        severity="error",
        recommended_action="Obtain prior authorization from the payer before resubmitting the claim",
        conditions=[
            {"field": "pa_required", "operator": "equals", "value": "true"},
            {"field": "pa_obtained", "operator": "equals", "value": "false"},
        ],
    ),
    RuleCreate(
        name="Authorization Number Required When PA Obtained",
        description="If prior authorization was obtained, the authorization number must be present on the claim",
        category="Authorization",
        severity="error",
        recommended_action="Add the prior authorization number to the claim before submission",
        conditions=[
            {"field": "pa_obtained", "operator": "equals", "value": "true"},
            {"field": "pa_number", "operator": "isEmpty"},
        ],
    ),
    RuleCreate(
        name="High Billed Amount Threshold",
        description="Claims with billed amounts exceeding $30,000 require additional review",
        category="Billing",
        severity="warning",
        recommended_action="Review charge detail and verify all line items are accurately coded and documented",
        conditions=[{"field": "total_charge", "operator": "greaterThan", "value": "30000"}],
    ),
    RuleCreate(
        name="Excessive Days in AR",
        description="Claims older than 60 days in accounts receivable need immediate attention",
        category="Billing",
        severity="warning",
        recommended_action="Escalate to collections team and follow up with payer on claim status",
        conditions=[{"field": "days_in_ar", "operator": "greaterThan", "value": "60"}],
    ),
    RuleCreate(
        name="Timely Filing Risk",
        description="Claims submitted more than 30 days after service risk exceeding payer filing limits",
        category="Billing",
        severity="warning",
        recommended_action="Submit immediately and confirm the payer's timely filing limit for this service date",
        conditions=[{"field": "days_to_submission", "operator": "greaterThan", "value": "30"}],
    ),
    RuleCreate(
        name="UnitedHealthcare Coding Compliance",
        description=(
            "UnitedHealthcare denies unspecified diagnosis codes for many procedures; "
            "ICD-10 codes with a .9 subcategory usually denote 'unspecified'"
        ),
        category="Payer-Specific",
        severity="warning",
        recommended_action="Update the diagnosis code to the highest specificity supported by documentation",
        scope={"type": "payer", "values": ["PAY004", "PAY005"]},
        conditions=[{"field": "primary_icd10", "operator": "contains", "value": ".9"}],
    ),
    RuleCreate(
        name="Non-Clean Claim Review",
        description="Claims flagged as not clean require review before submission to avoid preventable denials",
        category="Required Fields",
        severity="warning",
        recommended_action="Review claim for missing or incomplete fields and correct before submission",
        conditions=[{"field": "is_clean_claim", "operator": "equals", "value": "false"}],
    ),
    RuleCreate(
        name="High-Value Institutional Claim Review",
        description="Humana institutional claims over $20,000 require additional documentation review",
        category="Payer-Specific",
        severity="warning",
        recommended_action="Verify all supporting documentation is attached and coding matches clinical records",
        scope={"type": "payer", "values": ["PAY007"]},
        conditions=[
            {"field": "claim_type", "operator": "equals", "value": "Institutional"},
            {"field": "total_charge", "operator": "greaterThan", "value": "20000"},
        ],
    ),
    *CODING_RULES,
    *MISMATCH_RULES,
]
