"""Default validation rule set, loaded into the rule store at startup.

Ported from the prototype's defaultRules.js and recalibrated to the synthetic
dataset (e.g. the billed-amount threshold sits near the 99th percentile of
total_charge, ~$31.6K, rather than the prototype's $50K, which no claim reaches).
"""

from app.models import RuleCreate

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
]
