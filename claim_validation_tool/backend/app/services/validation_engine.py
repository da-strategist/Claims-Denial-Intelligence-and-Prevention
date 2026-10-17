"""Evaluates validation rules against claims.

Rules are evaluated column-wise on a pandas DataFrame of claims, so the same code
validates a page of 25 claims or tests a draft rule across all 120K in well under
a second.
"""

import pandas as pd

from app.models import (
    RULE_FIELDS,
    ClaimValidation,
    Condition,
    ConditionLogic,
    FieldType,
    Operator,
    Rule,
    RuleDefinition,
    RuleFinding,
    RuleScope,
    RuleTestResult,
    ScopeType,
    Severity,
    ValidationStatus,
)
from app.models.rule import SCOPE_COLUMNS, parse_condition_value
from app.services.risk_scorer import score_claim

# A claim with errors at or above this risk score is routed to the AI fix workflow
AI_FIX_RISK_THRESHOLD = 60

TEST_SAMPLE_SIZE = 20


def condition_mask(condition: Condition, claims: pd.DataFrame) -> pd.Series:
    """Boolean Series: which claims satisfy the condition."""
    spec = RULE_FIELDS[condition.field]
    column = claims[condition.field]

    if condition.operator in (Operator.IS_EMPTY, Operator.IS_NOT_EMPTY):
        empty = column.isna()
        if spec.type in (FieldType.STRING, FieldType.ENUM, FieldType.DATE):
            empty |= column.astype(str).str.strip() == ""
        return empty if condition.operator == Operator.IS_EMPTY else ~empty

    value = parse_condition_value(spec, condition.value)
    match condition.operator:
        case Operator.EQUALS:
            return column == value
        case Operator.NOT_EQUALS:
            return column != value
        case Operator.GREATER_THAN:
            # Dates are ISO-8601 strings, which compare correctly as text
            return column > value
        case Operator.LESS_THAN:
            return column < value
        case Operator.CONTAINS:
            return column.str.contains(value, case=False, regex=False)
    raise ValueError(f"Unsupported operator {condition.operator}")


def scope_mask(scope: RuleScope, claims: pd.DataFrame) -> pd.Series:
    """Boolean Series: which claims the rule applies to."""
    if scope.type == ScopeType.ALL:
        return pd.Series(True, index=claims.index)
    return claims[SCOPE_COLUMNS[scope.type]].isin(scope.values)


def rule_mask(rule: RuleDefinition, claims: pd.DataFrame) -> pd.Series:
    """Boolean Series: which claims the rule flags (in scope and conditions met)."""
    masks = [condition_mask(condition, claims) for condition in rule.conditions]
    if rule.condition_logic == ConditionLogic.OR:
        matched = pd.concat(masks, axis=1).any(axis=1)
    else:
        matched = pd.concat(masks, axis=1).all(axis=1)
    return matched & scope_mask(rule.scope, claims)


def validate_claims(claims: pd.DataFrame, rules: list[Rule]) -> list[ClaimValidation]:
    """Run the enabled rules against each claim and score its denial risk.

    `claims` is a frame from ClaimsRepository.claims_frame(); results are in the same order.
    """
    findings: dict[str, list[RuleFinding]] = {claim_id: [] for claim_id in claims["claim_id"]}
    # Fields the rules that flagged each claim test, so the scorer doesn't count them again
    flagged_fields: dict[str, set[str]] = {claim_id: set() for claim_id in claims["claim_id"]}
    for rule in rules:
        if not rule.enabled:
            continue
        finding = _finding(rule)
        fields = {condition.field for condition in rule.conditions}
        for claim_id in claims.loc[rule_mask(rule, claims), "claim_id"]:
            findings[claim_id].append(finding)
            flagged_fields[claim_id] |= fields

    results = []
    for claim in claims.to_dict("records"):
        claim_findings = findings[claim["claim_id"]]
        risk_score, risk_factors = score_claim(
            claim, claim_findings, flagged_fields[claim["claim_id"]]
        )
        results.append(
            ClaimValidation(
                claim_id=claim["claim_id"],
                status=_status(claim_findings, risk_score),
                risk_score=risk_score,
                risk_factors=risk_factors,
                findings=claim_findings,
            )
        )
    return results


def test_rule(rule: RuleDefinition, claims: pd.DataFrame) -> RuleTestResult:
    """How many claims a draft rule would flag, without saving it."""
    in_scope = scope_mask(rule.scope, claims)
    matched = rule_mask(rule, claims)
    return RuleTestResult(
        total_claims=len(claims),
        in_scope=int(in_scope.sum()),
        matched=int(matched.sum()),
        sample_claim_ids=claims.loc[matched, "claim_id"].head(TEST_SAMPLE_SIZE).tolist(),
    )


# Keep pytest from collecting test_rule as a test when the engine is imported in tests
test_rule.__test__ = False


def _finding(rule: Rule) -> RuleFinding:
    return RuleFinding(
        rule_id=rule.id,
        rule_name=rule.name,
        severity=rule.severity,
        category=rule.category,
        message=rule.description,
        recommended_action=rule.recommended_action,
    )


def _status(findings: list[RuleFinding], risk_score: int) -> ValidationStatus:
    severities = {finding.severity for finding in findings}
    if Severity.ERROR in severities:
        if risk_score >= AI_FIX_RISK_THRESHOLD:
            return ValidationStatus.AI_FIX
        return ValidationStatus.ERROR
    if Severity.WARNING in severities:
        return ValidationStatus.WARNING
    return ValidationStatus.PASS
