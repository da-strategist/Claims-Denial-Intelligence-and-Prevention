"""AI Fix: suggests how to resolve a claim's validation findings and applies accepted fixes.

Suggestions come from a FixSuggester. The demo uses RuleBasedSuggester, which is
deterministic and cites reference data. A retrieval-augmented (RAG) suggester for
ambiguous cases (Phase 10) can implement the same interface and run alongside it.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from pydantic import ValidationError

from app.data import ClaimsRepository, CorrectionStore, ReferenceData, RuleRepository
from app.data.reference import contract_rate
from app.models import (
    RULE_FIELDS,
    Citation,
    Claim,
    ClaimDetail,
    ClaimFixes,
    ClaimValidation,
    ClarificationTopic,
    Confidence,
    Correction,
    FixSuggestion,
    ProposedChange,
    Rule,
    Severity,
    SourceType,
    SuggestionAction,
)
from app.models.rule import parse_condition_value
from app.services import validation_engine

SEVERITY_ORDER = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}

# Plain-language messages for format errors on correctable fields
FORMAT_HINTS = {"primary_icd10": "must be an ICD-10 code such as E11.65 or I10"}


@dataclass(frozen=True)
class ClaimContext:
    """Everything a suggester may look at for one claim."""

    claim: ClaimDetail
    validation: ClaimValidation
    rules: dict[str, Rule]
    reference: ReferenceData


class FixSuggester(Protocol):
    name: str

    def suggest(self, context: ClaimContext) -> list[FixSuggestion]: ...


class SuggestionError(ValueError):
    """An accepted fix can't be applied (wrong action, missing or invalid value)."""


# --- Rule-based suggester ------------------------------------------------------


def _has(rule: Rule, field: str, operator: str, value: str | None = None) -> bool:
    return any(
        c.field == field
        and c.operator == operator
        and (value is None or (c.value or "").lower() == value)
        for c in rule.conditions
    )


def _kind(rule: Rule) -> str:
    """What a rule checks, judged from its conditions (rule IDs can change)."""
    if _has(rule, "pa_required", "equals", "true") and _has(rule, "pa_obtained", "equals", "false"):
        return "missing_prior_auth"
    if _has(rule, "pa_obtained", "equals", "true") and _has(rule, "pa_number", "isEmpty"):
        return "missing_pa_number"
    if _has(rule, "primary_icd10", "isEmpty"):
        return "missing_diagnosis"
    if _has(rule, "primary_icd10", "contains"):
        return "diagnosis_specificity"
    if _has(rule, "is_clean_claim", "equals", "false"):
        return "non_clean"
    if _has(rule, "total_charge", "greaterThan"):
        return "high_charge"
    if _has(rule, "days_in_ar", "greaterThan"):
        return "ar_followup"
    if _has(rule, "days_to_submission", "greaterThan"):
        return "timely_filing"
    return "generic"


def _as_str(value) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _change(claim: ClaimDetail, field: str, suggested: str | None = None, options=None):
    spec = RULE_FIELDS[field]
    return ProposedChange(
        field=field,
        label=spec.label,
        type=spec.type,
        current_value=_as_str(getattr(claim, field)),
        suggested_value=suggested,
        options=options,
    )


def _rule_citation(rule: Rule) -> Citation:
    return Citation(
        source_type=SourceType.RULE,
        reference_id=rule.id,
        title=rule.name,
        excerpt=rule.description,
    )


def _payer_citation(claim: ClaimDetail) -> list[Citation]:
    payer = claim.payer
    if payer is None:
        return []
    return [
        Citation(
            source_type=SourceType.PAYER,
            reference_id=payer.payer_id,
            title=payer.payer_name,
            excerpt=(
                f"{payer.payer_type}; denial rate {payer.denial_rate:.0%}; "
                f"pays in {payer.avg_days_to_pay} days on average; "
                f"prior-auth strictness {payer.pa_strictness:.0%}"
            ),
        )
    ]


def _icd10_citation(reference: ReferenceData, code: str) -> list[Citation]:
    entry = reference.icd10.get(code)
    if entry is None:
        return []
    return [
        Citation(
            source_type=SourceType.ICD10,
            reference_id=code,
            title=entry["description"],
            excerpt=f"{entry['body_system']} · {entry['acuity_type']}",
        )
    ]


class RuleBasedSuggester:
    name = "rule_based"

    def suggest(self, context: ClaimContext) -> list[FixSuggestion]:
        findings = sorted(context.validation.findings, key=lambda f: SEVERITY_ORDER[f.severity])
        suggestions = []
        for finding in findings:
            rule = context.rules.get(finding.rule_id)
            if rule is not None:
                handler = getattr(self, f"_{_kind(rule)}")
                suggestions.append(handler(context, rule))
        suggestions.extend(self._appeals(context))
        return suggestions

    def _base(self, context: ClaimContext, rule: Rule, **fields) -> FixSuggestion:
        citations = fields.pop("citations", [])
        return FixSuggestion(
            id=f"{context.claim.claim_id}:{rule.id}",
            claim_id=context.claim.claim_id,
            rule_id=rule.id,
            citations=[*citations, _rule_citation(rule)],
            source=self.name,
            **fields,
        )

    def _missing_diagnosis(self, context: ClaimContext, rule: Rule) -> FixSuggestion:
        claim = context.claim
        pointers = Counter(line.icd10_pointer for line in claim.lines)
        if not pointers:
            return self._base(
                context,
                rule,
                title="Enter the primary diagnosis",
                summary="No diagnosis is recorded on the claim or its lines.",
                reasoning="There is nothing on the claim to derive the diagnosis from.",
                steps=["Review the encounter's clinical documentation", "Enter the ICD-10 code"],
                action=SuggestionAction.APPLY,
                confidence=Confidence.LOW,
                changes=[_change(claim, "primary_icd10")],
            )
        code, count = pointers.most_common(1)[0]
        unanimous = count == len(claim.lines)
        return self._base(
            context,
            rule,
            title=f"Set primary diagnosis to {code}",
            summary=f"{count} of {len(claim.lines)} claim lines point to {code}.",
            reasoning=(
                "The claim lines already carry diagnosis pointers. Using the code they point to "
                "keeps the header consistent with the lines."
                + ("" if unanimous else " The lines disagree, so confirm against documentation.")
            ),
            steps=["Confirm the code matches the clinical documentation", "Apply the fix"],
            action=SuggestionAction.APPLY,
            confidence=Confidence.HIGH if unanimous else Confidence.MEDIUM,
            changes=[_change(claim, "primary_icd10", code, options=sorted(pointers))],
            citations=[
                Citation(
                    source_type=SourceType.CLAIM_DATA,
                    reference_id=line.line_id,
                    title=f"Line {line.line_number} · CPT {line.cpt_code}",
                    excerpt=f"Diagnosis pointer {line.icd10_pointer}",
                )
                for line in claim.lines
            ]
            + _icd10_citation(context.reference, code),
        )

    def _missing_prior_auth(self, context: ClaimContext, rule: Rule) -> FixSuggestion:
        claim = context.claim
        payer_name = claim.payer.payer_name if claim.payer else claim.payer_id
        strict = claim.payer is not None and claim.payer.pa_strictness >= 0.5
        return self._base(
            context,
            rule,
            title=f"Obtain prior authorization from {payer_name}",
            summary="Prior authorization was required but not obtained.",
            reasoning=(
                f"{payer_name} requires authorization for this service. Payers often accept a "
                "retroactive request with supporting documentation"
                + (", but this payer enforces prior auth strictly." if strict else ".")
                + " Only record the authorization once the payer has issued a number."
            ),
            steps=[
                f"Check the {payer_name} portal for an existing authorization for {claim.service_date}",
                "If none, submit a retro-authorization request with clinical documentation",
                "Enter the authorization number below and apply",
            ],
            action=SuggestionAction.APPLY,
            confidence=Confidence.LOW if strict else Confidence.MEDIUM,
            changes=[_change(claim, "pa_obtained", "true"), _change(claim, "pa_number")],
            citations=_payer_citation(claim),
            clarification_topic=ClarificationTopic.PAYER_PRIOR_AUTH,
        )

    def _missing_pa_number(self, context: ClaimContext, rule: Rule) -> FixSuggestion:
        claim = context.claim
        payer_name = claim.payer.payer_name if claim.payer else claim.payer_id
        return self._base(
            context,
            rule,
            title="Add the prior authorization number",
            summary="Authorization was obtained but its number isn't on the claim.",
            reasoning="Payers match claims to authorizations by number; without it the claim is denied.",
            steps=[
                f"Look up the authorization in the {payer_name} portal for {claim.service_date}",
                "Enter the number below and apply",
            ],
            action=SuggestionAction.APPLY,
            confidence=Confidence.MEDIUM,
            changes=[_change(claim, "pa_number")],
            citations=_payer_citation(claim),
        )

    def _diagnosis_specificity(self, context: ClaimContext, rule: Rule) -> FixSuggestion:
        claim = context.claim
        siblings = context.reference.icd10_siblings(claim.primary_icd10)
        return self._base(
            context,
            rule,
            title="Use a more specific diagnosis code",
            summary=f"{claim.primary_icd10} is likely an unspecified code for this payer.",
            reasoning=(
                "Unspecified codes are a common denial trigger. Only code to a higher specificity "
                "when the clinical documentation supports it."
                + (f" Known codes in the same category: {', '.join(siblings)}." if siblings else "")
            ),
            steps=[
                "Review the provider's documentation for laterality, severity, or complications",
                "Query the provider if documentation is unclear",
                "Enter the more specific code and apply",
            ],
            action=SuggestionAction.APPLY,
            confidence=Confidence.LOW,
            changes=[_change(claim, "primary_icd10", options=siblings or None)],
            citations=_icd10_citation(context.reference, claim.primary_icd10)
            + _payer_citation(claim),
            clarification_topic=ClarificationTopic.MEDICAL_NECESSITY,
        )

    def _non_clean(self, context: ClaimContext, rule: Rule) -> FixSuggestion:
        return self._base(
            context,
            rule,
            title="Scrub the claim and mark it clean",
            summary="The claim failed pre-submission edits.",
            reasoning=(
                "Non-clean claims are denied far more often. Mark the claim clean only after "
                "every item below has been checked and corrected."
            ),
            steps=[
                "Verify patient demographics and subscriber ID",
                "Check codes, modifiers, and units on every line",
                "Confirm required attachments are present",
                "Apply to mark the claim clean",
            ],
            action=SuggestionAction.APPLY,
            confidence=Confidence.MEDIUM,
            changes=[_change(context.claim, "is_clean_claim", "true")],
        )

    def _high_charge(self, context: ClaimContext, rule: Rule) -> FixSuggestion:
        claim = context.claim
        expected, citations = 0.0, []
        for category in sorted({line.cpt_category for line in claim.lines}):
            rate = contract_rate(context.reference, claim.payer_id, category)
            charge = sum(l.charge_amount for l in claim.lines if l.cpt_category == category)
            if rate is None:
                continue
            expected += charge * rate
            contract = context.reference.contracts[(claim.payer_id, category)]
            citations.append(
                Citation(
                    source_type=SourceType.PAYER_CONTRACT,
                    reference_id=contract["contract_id"],
                    title=f"{category} contract",
                    excerpt=f"Reimburses {rate:.1%} of charges (${charge:,.2f} billed)",
                )
            )
        expectation = (
            f" Contracted rates put expected payment at about ${expected:,.2f}."
            if citations
            else " No active contract rates were found for these services."
        )
        return self._base(
            context,
            rule,
            title="Review high-value charges before submission",
            summary=f"Billed ${claim.total_charge:,.2f} exceeds the review threshold.",
            reasoning="High-value claims draw payer audits; errors here are costly." + expectation,
            steps=[
                "Verify each line's code, units, and charge against the documentation",
                "Attach operative or procedure notes",
                "Confirm the charge master prices are current",
            ],
            action=SuggestionAction.MANUAL,
            confidence=Confidence.MEDIUM,
            citations=citations + _payer_citation(claim),
        )

    def _ar_followup(self, context: ClaimContext, rule: Rule) -> FixSuggestion:
        claim = context.claim
        typical = claim.payer.avg_days_to_pay if claim.payer else None
        return self._base(
            context,
            rule,
            title="Follow up with the payer on claim status",
            summary=f"The claim has been in AR for {claim.days_in_ar} days.",
            reasoning=(
                f"This payer typically pays in {typical} days." if typical else "Aging claims lose value."
            )
            + " Follow up before the claim ages further.",
            steps=[
                "Check claim status in the payer portal or by phone",
                "Resolve any pending information requests",
                "Escalate to collections if the payer is unresponsive",
            ],
            action=SuggestionAction.MANUAL,
            confidence=Confidence.MEDIUM,
            citations=_payer_citation(claim),
        )

    def _timely_filing(self, context: ClaimContext, rule: Rule) -> FixSuggestion:
        claim = context.claim
        lag = (claim.submission_date - claim.service_date).days
        return self._base(
            context,
            rule,
            title="Confirm the payer's timely filing limit",
            summary=f"Submitted {lag} days after the service date.",
            reasoning="Claims filed after the payer's limit are denied and usually can't be appealed.",
            steps=[
                "Check this payer's filing limit in the contract",
                "Submit immediately, with proof of timely filing if the limit is close",
            ],
            action=SuggestionAction.MANUAL,
            confidence=Confidence.MEDIUM,
            citations=_payer_citation(claim),
        )

    def _generic(self, context: ClaimContext, rule: Rule) -> FixSuggestion:
        return self._base(
            context,
            rule,
            title=f"Review: {rule.name}",
            summary=rule.description or "This claim matched a custom rule.",
            reasoning="This is a custom rule; follow its recommended action.",
            steps=[rule.recommended_action] if rule.recommended_action else [],
            action=SuggestionAction.MANUAL,
            confidence=Confidence.LOW,
        )

    def _appeals(self, context: ClaimContext) -> list[FixSuggestion]:
        claim, reference = context.claim, context.reference
        suggestions = []
        for denial in claim.denials:
            citations = []
            if carc := reference.carc.get(denial.carc_code):
                citations.append(
                    Citation(
                        source_type=SourceType.CARC,
                        reference_id=denial.carc_code,
                        title=f"CARC {denial.carc_code}",
                        excerpt=f"{carc['description']} (group {carc['group_code']})",
                    )
                )
            if rarc := reference.rarc.get(denial.rarc_code):
                citations.append(
                    Citation(
                        source_type=SourceType.RARC,
                        reference_id=denial.rarc_code,
                        title=f"RARC {denial.rarc_code}",
                        excerpt=rarc["description"],
                    )
                )
            suggestions.append(
                FixSuggestion(
                    id=f"{claim.claim_id}:appeal:{denial.denial_id}",
                    claim_id=claim.claim_id,
                    title="Correct and appeal the denial",
                    summary=f"{denial.denial_reason_text} — ${denial.denial_amount:,.2f} denied.",
                    reasoning=(
                        f"Root cause: {denial.root_cause_category}"
                        + (" (preventable)." if denial.is_preventable else ".")
                        + " Fix the root cause first, then appeal citing the adjustment codes."
                    ),
                    steps=[
                        "Resolve the root cause using the fixes above",
                        "Gather supporting documentation",
                        f"Submit a corrected claim or appeal referencing CARC {denial.carc_code}"
                        f" / RARC {denial.rarc_code}",
                    ],
                    action=SuggestionAction.CLARIFY,
                    confidence=Confidence.LOW,
                    citations=citations,
                    clarification_topic=ClarificationTopic.APPEAL,
                    source=self.name,
                )
            )
        return suggestions


def get_suggester() -> FixSuggester:
    """The suggester the API uses. Phase 10 can combine this with a RAG suggester."""
    return RuleBasedSuggester()


# --- Orchestration --------------------------------------------------------------


def claim_fixes(
    claim_id: str,
    claims: ClaimsRepository,
    rules: RuleRepository,
    corrections: CorrectionStore,
    reference: ReferenceData,
    suggester: FixSuggester,
) -> ClaimFixes | None:
    claim = claims.get_claim(claim_id)
    if claim is None:
        return None
    rule_list = rules.list()
    [validation] = validation_engine.validate_claims(claims.claims_frame([claim_id]), rule_list)
    context = ClaimContext(
        claim=claim,
        validation=validation,
        rules={rule.id: rule for rule in rule_list},
        reference=reference,
    )
    return ClaimFixes(
        claim_id=claim_id,
        validation=validation,
        suggestions=suggester.suggest(context),
        corrections=corrections.for_claim(claim_id),
    )


def resolve_changes(
    claim: ClaimDetail, suggestion: FixSuggestion, values: dict[str, str]
) -> dict[str, tuple[str | None, str]]:
    """Validate the values for an accepted suggestion. Returns {field: (old, new)}."""
    if suggestion.action != SuggestionAction.APPLY:
        raise SuggestionError(f"Suggestion {suggestion.id} is {suggestion.action}, not applicable")
    unknown = set(values) - {change.field for change in suggestion.changes}
    if unknown:
        raise SuggestionError(f"Not part of this fix: {', '.join(sorted(unknown))}")

    changes: dict[str, tuple[str | None, str]] = {}
    typed: dict[str, object] = {}
    for change in suggestion.changes:
        raw = (values.get(change.field) or change.suggested_value or "").strip()
        if not raw:
            raise SuggestionError(f"{change.label} is required")
        try:
            typed[change.field] = parse_condition_value(RULE_FIELDS[change.field], raw)
        except ValueError as err:
            raise SuggestionError(str(err)) from None
        new_value = _as_str(typed[change.field])
        if new_value != change.current_value:
            changes[change.field] = (change.current_value, new_value)

    # A fix that leaves every field as it was would mark the claim corrected for nothing
    if not changes:
        labels = ", ".join(f"{c.label} is already {c.current_value}" for c in suggestion.changes)
        raise SuggestionError(f"Nothing to change: {labels}. Enter a different value to apply.")

    # Re-validate the corrected claim header (e.g. ICD-10 format)
    try:
        Claim.model_validate({**claim.model_dump(), **typed})
    except ValidationError as err:
        problems = []
        for e in err.errors():
            field = str(e["loc"][0])
            label = RULE_FIELDS[field].label if field in RULE_FIELDS else field
            problems.append(f"{label} {FORMAT_HINTS.get(field, e['msg'])}")
        raise SuggestionError("; ".join(problems)) from None
    return changes


def apply_fix(
    claim_id: str,
    suggestion_id: str,
    values: dict[str, str],
    claims: ClaimsRepository,
    rules: RuleRepository,
    corrections: CorrectionStore,
    reference: ReferenceData,
    suggester: FixSuggester,
    applied_by: str | None = None,
) -> tuple[ClaimValidation, list[Correction], ClaimFixes]:
    """Apply an accepted suggestion, then re-validate. Returns (before, applied, after)."""
    before = claim_fixes(claim_id, claims, rules, corrections, reference, suggester)
    if before is None:
        raise LookupError(f"Claim {claim_id} not found")
    suggestion = next((s for s in before.suggestions if s.id == suggestion_id), None)
    if suggestion is None:
        raise LookupError(f"Suggestion {suggestion_id} is not current for {claim_id}")

    changes = resolve_changes(claims.get_claim(claim_id), suggestion, values)
    applied = corrections.add(claim_id, suggestion_id, changes, applied_by)
    claims.apply_overrides(corrections.overrides())
    after = claim_fixes(claim_id, claims, rules, corrections, reference, suggester)
    return before.validation, applied, after


def undo_corrections(
    claim_id: str,
    claims: ClaimsRepository,
    rules: RuleRepository,
    corrections: CorrectionStore,
    reference: ReferenceData,
    suggester: FixSuggester,
) -> ClaimFixes | None:
    corrections.clear_claim(claim_id)
    claims.apply_overrides(corrections.overrides())
    return claim_fixes(claim_id, claims, rules, corrections, reference, suggester)
