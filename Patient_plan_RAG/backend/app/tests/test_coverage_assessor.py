"""Edge cases for the coverage classifier (multi-policy cases are in the eval)."""

from backend.app.models.policy import DocumentChunk
from backend.app.services.coverage_assessor import assess_coverage


def _chunk(section, content, page=1):
    return DocumentChunk(chunk_id=f"{section[:6]}{page}", document_id="d",
                         page_number=page, section_heading=section, content=content)


POLICY = [
    _chunk("COVERED SERVICES", "COVERED SERVICES\n"
           "DIAGNOSTIC IMAGING: X-rays covered at 80%. Advanced imaging (MRI, CT) requires prior "
           "authorization.\nHOSPICE CARE: Covered at 100% in-network.\n"
           "REHABILITATION: Physical therapy covered, limited to 30 visits per year."),
    _chunk("PRIOR AUTHORIZATION REQUIREMENTS", "PRIOR AUTHORIZATION REQUIREMENTS\n"
           "• Bariatric surgery\n• Genetic testing", page=2),
    _chunk("EXCLUSIONS AND LIMITATIONS", "EXCLUSIONS AND LIMITATIONS\n"
           "• Weight loss programs (unless part of approved bariatric surgery program)\n"
           "• Acupuncture, naturopathy, and homeopathy\n"
           "• Dental services (covered under separate dental plan)", page=3),
]


def _assess(service, code=""):
    return assess_coverage(service, code, POLICY)


def test_prior_auth_from_paragraph_text():
    r = _assess("MRI")
    assert (r.classification, r.prior_auth_required) == ("conditional_coverage", True)
    assert "requires prior authorization" in r.explanation


def test_prior_auth_from_section_bullet():
    r = _assess("Genetic testing")
    assert (r.classification, r.prior_auth_required) == ("conditional_coverage", True)


def test_exclusion_bullet_main_item():
    r = _assess("Acupuncture")
    assert (r.classification, r.prior_auth_required) == ("exclusion_identified", False)
    assert r.exclusions == ["• Acupuncture, naturopathy, and homeopathy"]


def test_mention_inside_exclusion_parenthetical_is_not_an_exclusion():
    # bariatric surgery is only *mentioned* in the weight-loss exclusion
    r = _assess("Bariatric surgery")
    assert (r.classification, r.prior_auth_required) == ("conditional_coverage", True)


def test_plain_coverage_and_other_conditions():
    assert _assess("Hospice care").classification == "coverage_indicated"
    r = _assess("Physical therapy")
    assert (r.classification, r.prior_auth_required) == ("conditional_coverage", False)


def test_unknown_words_dropped_when_most_of_service_is_named():
    assert _assess("knee MRI").classification == "conditional_coverage"


def test_service_not_named_is_insufficient():
    for service in ("Laser tattoo removal", "Chiropractic care"):
        r = _assess(service)
        assert r.classification == "insufficient_information"
        assert r.prior_auth_required is None and r.citations == []


def test_service_code_is_not_required_in_policy_text():
    assert _assess("MRI", "70551").classification == "conditional_coverage"
