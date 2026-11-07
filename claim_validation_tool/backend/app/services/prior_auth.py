"""What a claim's checks do and don't cover, so a clean result isn't read as more than it is."""

from app.data.prior_auth_lists import PriorAuthListStore
from app.models import ClaimDetail, CoverageCheck, PayerType, PriorAuthCheck


def _self_pay(claim: ClaimDetail) -> bool:
    return claim.payer is not None and claim.payer.payer_type == PayerType.SELF_PAY


def coverage_check(claim: ClaimDetail) -> CoverageCheck:
    """Whether the patient's coverage was active needs an eligibility check with the payer,
    which isn't built, so it's never been checked here."""
    return CoverageCheck.NOT_APPLICABLE if _self_pay(claim) else CoverageCheck.NOT_CHECKED


def prior_auth_check(claim: ClaimDetail, lists: PriorAuthListStore) -> PriorAuthCheck:
    if claim.pa_required:
        return PriorAuthCheck.OBTAINED if claim.pa_obtained else PriorAuthCheck.MISSING
    if _self_pay(claim):
        return PriorAuthCheck.NOT_APPLICABLE
    if not lists.has_list(claim.payer_id):
        return PriorAuthCheck.NOT_ASSESSED
    # On the list but not marked: the claim was saved before the list was, and hasn't been
    # checked against it. Sending or editing it again does that.
    codes = [line.cpt_code for line in claim.lines]
    return PriorAuthCheck.NOT_ASSESSED if lists.listed_codes(claim.payer_id, codes) else PriorAuthCheck.NOT_NEEDED
