"""How a claim differs from what was first entered or uploaded, for the billing system.

A biller needs the net result (this field was X, it's now Y), so a value changed twice shows
once and a value changed back doesn't show at all. Values are the real claim values, PHI
included: this list is for people allowed the claim file, never for the audit log.
"""

from collections.abc import Iterable
from datetime import datetime

from app.models import ClaimChange, ClaimChangeSource, ClaimDetail, Correction

_HEADER_LABELS = {
    "payer": "Payer",
    "other_payers": "Other coverage",
    "provider": "Provider",
    "facility": "Facility",
    "claim_type": "Claim type",
    "place_of_service": "Place of service",
    "service_date": "Service date",
    "primary_icd10": "Primary diagnosis",
    "additional_icd10": "Other diagnoses",
    "pa_required": "Prior auth required",
    "pa_obtained": "Prior auth obtained",
    "pa_number": "Prior auth number",
    "total_charge": "Total charge",
}
_LINE_LABELS = {
    "cpt_code": "CPT",
    "modifier": "modifier",
    "units": "units",
    "charge_amount": "charge",
    "icd10_pointer": "diagnosis pointer",
    "revenue_code": "revenue code",
}
# AI Fix corrections by field name, in the same terms as an edit so the two can be netted.
# is_clean_claim isn't here: it's our own flag, with nothing to change in a billing system.
_CORRECTION_FIELDS = {"primary_icd10", "pa_obtained", "pa_number"}


def _display(value: object) -> str | None:
    if value is None or value == "" or value == []:
        return None
    if value is True or value == "true":
        return "Yes"
    if value is False or value == "false":
        return "No"
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def _flatten(prefix: str, value: object, into: dict[str, str | None]) -> None:
    """Billing details as one entry per value: "billing.policy.member_id" -> "M123"."""
    if isinstance(value, dict):
        for key, item in value.items():
            _flatten(f"{prefix}.{key}", item, into)
    elif isinstance(value, list):
        for number, item in enumerate(value, start=1):
            _flatten(f"{prefix}.{number}", item, into)
    else:
        into[prefix] = _display(value)


def _named(identifier: str, name: str | None) -> str:
    return f"{name} ({identifier})" if name else identifier


def claim_values(claim: ClaimDetail, repo) -> dict[str, str | None]:
    """Everything on the claim a billing system holds, by field key."""
    payer = claim.payer.payer_name if claim.payer else None
    provider = claim.provider.provider_name if claim.provider else None
    facility = repo.get_facility(claim.facility_id)
    others = [repo.get_payer(payer_id) for payer_id in claim.other_payer_ids]
    values: dict[str, str | None] = {
        "payer": _named(claim.payer_id, payer),
        "other_payers": ", ".join(_named(p.payer_id, p.payer_name) for p in others if p) or None,
        "provider": _named(claim.provider_id, provider),
        "facility": _named(claim.facility_id, facility.facility_name if facility else None),
    }
    dumped = claim.model_dump(mode="json")
    for key in _HEADER_LABELS:
        if key not in values:
            values[key] = _display(dumped[key])
    for number, line in enumerate(dumped["lines"], start=1):
        for key in _LINE_LABELS:
            values[f"line.{number}.{key}"] = _display(line.get(key))
    if dumped.get("billing"):
        _flatten("billing", dumped["billing"], values)
    return values


def label(field: str) -> str:
    """Words for a field key: "line.2.units" -> "Line 2 units"."""
    if field in _HEADER_LABELS:
        return _HEADER_LABELS[field]
    parts = field.split(".")
    if parts[0] == "line":
        return f"Line {parts[1]} {_LINE_LABELS[parts[2]]}"
    words = [p.replace("_", " ") for p in parts[1:]]
    text = " ".join(words).replace("zip code", "ZIP code").replace(" id", " ID")
    return text[0].upper() + text[1:]


def edit_changes(
    before: dict[str, str | None], after: dict[str, str | None], by: str, at: datetime
) -> list[ClaimChange]:
    return [
        ClaimChange(
            field=field,
            label=label(field),
            old_value=before.get(field),
            new_value=after.get(field),
            source=ClaimChangeSource.EDIT,
            changed_by=by,
            changed_at=at,
        )
        for field in [*before, *(f for f in after if f not in before)]
        if before.get(field) != after.get(field)
    ]


def correction_changes(corrections: Iterable[Correction]) -> list[ClaimChange]:
    return [
        ClaimChange(
            field=c.field,
            label=label(c.field),
            old_value=_display(c.old_value),
            new_value=_display(c.new_value),
            source=ClaimChangeSource.AI_FIX,
            changed_by=c.applied_by,
            changed_at=c.applied_at,
        )
        for c in corrections
        if c.field in _CORRECTION_FIELDS
    ]


def net_changes(changes: Iterable[ClaimChange]) -> list[ClaimChange]:
    """One entry per field: its first old value and the last change made to it. A field
    that ended where it started is left out."""
    net: dict[str, ClaimChange] = {}
    for change in sorted(changes, key=lambda c: c.changed_at):
        first = net.get(change.field)
        net[change.field] = (
            change if first is None else change.model_copy(update={"old_value": first.old_value})
        )
    return [c for c in net.values() if c.old_value != c.new_value]
