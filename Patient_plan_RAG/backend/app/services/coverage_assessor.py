"""Classify a service's coverage from the policy passages that name it.

Retrieval finds candidate chunks; the classification then looks only at the
paragraphs that actually mention the service:
- the main item of a bullet in an exclusions section  → exclusion identified
- in a prior-auth section, or its paragraph mentions
  authorization / precertification / approval         → conditional, prior auth
- its paragraph states other conditions               → conditional
- otherwise                                           → coverage indicated
If the policy never names the service: insufficient information.
"""

from ..models.coverage import CoverageAssessment, CoverageClassification, SourceCitation
from ..models.policy import DocumentChunk
from .policy_summarizer import _paragraphs, _split_parenthetical
from .retrieval import _tokenize, retrieve

_EXCLUSION_HEADINGS = ("exclusion", "not covered", "do not cover", "does not cover", "not cover")
_PRIOR_AUTH_HEADINGS = ("prior auth", "precertification", "pre-certification",
                        "preauthorization", "approval")
_PRIOR_AUTH_TEXT = ("authorization", "precertification", "pre-certification",
                    "preauthorization", "approval")
_CONDITION_TEXT = ("requires", "required", "must", "limited to", "referral", "only when")
# Words too generic to identify a service on their own (stemmed forms)
_GENERIC_WORDS = frozenset({
    "care", "service", "treatment", "therapy", "visit", "program", "procedure",
    "test", "testing", "exam", "health", "medical", "plan", "coverage", "benefit",
})


def _service_tokens(service_name: str, chunks: list[DocumentChunk]) -> set[str]:
    """Service words to match. Words the policy never uses are dropped when at
    least half the words remain and one of them is specific ("knee MRI" →
    MRI); otherwise all are kept, so the service counts as not named
    ("laser tattoo removal", "chiropractic care" must not match "care")."""
    tokens = set(_tokenize(service_name))
    known = set().union(*(_tokenize(c.content) for c in chunks)) if chunks else set()
    present = tokens & known
    if present and len(present) * 2 >= len(tokens) and present - _GENERIC_WORDS:
        return present
    return tokens


def _insufficient(service_name: str, service_code: str) -> CoverageAssessment:
    return CoverageAssessment(
        service_name=service_name,
        service_code=service_code,
        classification=CoverageClassification.INSUFFICIENT,
        explanation=(
            "Insufficient policy evidence was found to assess coverage for "
            f"'{service_name}'. The policy may not specifically address "
            "this service, or it may be listed under different terminology."
        ),
        missing_information=["Policy may not address this service explicitly"],
        recommended_steps=[
            "Contact plan administrator for coverage verification",
            "Request a predetermination of benefits",
        ],
    )


def assess_coverage(
    service_name: str,
    service_code: str,
    chunks: list[DocumentChunk],
) -> CoverageAssessment:
    """Assess whether a service is covered, citing the passages used."""
    # Search on the service alone: generic words like "coverage"/"benefit"
    # would outrank it (they match the plan title).
    results = retrieve(f"{service_name} {service_code}", chunks, top_k=6)
    service = _service_tokens(service_name, chunks)
    if not results or not service:
        return _insufficient(service_name, service_code)

    # Paragraphs in the retrieved chunks that name the service
    mentions: list[tuple[DocumentChunk, str]] = []
    for chunk, _ in results:
        for para in _paragraphs(chunk.content.split("\n")):
            if service <= set(_tokenize(para)):
                mentions.append((chunk, para))
    if not mentions:
        return _insufficient(service_name, service_code)

    def heading_has(chunk: DocumentChunk, keywords: tuple[str, ...]) -> bool:
        return any(k in chunk.section_heading.lower() for k in keywords)

    exclusions = [
        (c, p) for c, p in mentions
        if heading_has(c, _EXCLUSION_HEADINGS) and p.startswith("•")
        and service <= set(_tokenize(_split_parenthetical(p.lstrip("• "))[0]))
    ]
    prior_auth = [
        (c, p) for c, p in mentions
        if heading_has(c, _PRIOR_AUTH_HEADINGS) or any(t in p.lower() for t in _PRIOR_AUTH_TEXT)
    ]
    conditional = [(c, p) for c, p in mentions if any(t in p.lower() for t in _CONDITION_TEXT)]

    if exclusions:
        classification, deciding = CoverageClassification.EXCLUDED, exclusions[0]
    elif prior_auth:
        classification, deciding = CoverageClassification.CONDITIONAL, prior_auth[0]
    elif conditional:
        classification, deciding = CoverageClassification.CONDITIONAL, conditional[0]
    else:
        classification, deciding = CoverageClassification.COVERED, mentions[0]

    citations = [
        SourceCitation(
            document_id=chunk.document_id,
            page_number=chunk.page_number,
            section=chunk.section_heading,
            from_scan=bool(chunk.metadata.get("from_scan")),
            excerpt=chunk.content[:250],
            confidence="supported" if score > 0.3 else "interpreted",
        )
        for chunk, score in results
    ]
    deciding_chunk, deciding_para = deciding
    return CoverageAssessment(
        service_name=service_name,
        service_code=service_code,
        classification=classification,
        explanation=(
            f"Based on policy evidence from section "
            f"'{deciding_chunk.section_heading or 'General'}' "
            f"(page {deciding_chunk.page_number or '?'}), {service_name} appears to be "
            f"{classification.value.replace('_', ' ')}: \"{deciding_para[:200]}\" "
            "Review the cited passages for full context."
        ),
        conditions=[p[:200] for _, p in (prior_auth + conditional)][:3],
        exclusions=[p[:200] for _, p in exclusions][:3],
        prior_auth_required=bool(prior_auth) and not exclusions,
        citations=citations,
        recommended_steps=[
            "Verify with plan administrator",
            "Check for applicable medical necessity criteria",
        ],
    )
