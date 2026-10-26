# Updated Product Audit Checklist --- AI Health Insurance Coverage Platform

## Purpose and scope

Audit the **existing application** against its current intended scope:
**Phase 1 is a prototype that uses user-uploaded insurance policy and
benefit documents to test reliable document understanding and question
answering.** The longer-term product is expected to incorporate
insurer-specific online sources and official regulatory resources
(including CMS), then potentially support provider
authorization-readiness workflows.

Do not assume that future-phase functionality must already exist in the
Phase 1 prototype. Assess current implementation and future readiness
separately.

### Status definitions

Assign exactly one status to each applicable item:

-   **PASS** --- Implemented and verified to work.
-   **PARTIAL** --- Implemented but incomplete or unreliable.
-   **FAIL** --- Expected for the current phase but missing, broken, or
    materially incorrect.
-   **N/A** --- Not applicable to the current phase or product scope.
-   **UNVERIFIED** --- Cannot confirm without further inspection or
    testing.

Do not mark an item PASS just because a UI component exists. Verify
behavior using code, workflows, tests, or a demonstration. Do not
rebuild the application during the audit.

For every item, label its scope as **Phase 1 --- current prototype**,
**Phase 2 --- external sources**, **Phase 3 --- provider workflow**, or
**Cross-phase foundation**. For future-phase items, report
readiness/design observations separately; do not count a planned feature
as a Phase 1 failure unless it is required for the current prototype.

------------------------------------------------------------------------

## 1. Phase 1 --- Document Upload and Processing

-   [ ] Users can upload insurance policies and benefit documents.
-   [ ] Supported file types, file-size limits, and upload constraints
    are clearly handled.
-   [ ] Upload and processing failures produce understandable error
    messages.
-   [ ] PDFs with selectable text are parsed correctly.
-   [ ] Scanned documents are handled through OCR where required, or
    clearly identified as unsupported.
-   [ ] Relevant policy sections are extracted without losing important
    conditions, exceptions, tables, or footnotes.
-   [ ] Document name, page number, and supporting source text are
    preserved for citations.
-   [ ] Available plan identifiers (such as payer, plan name, and
    effective dates) are extracted or flagged as unavailable.
-   [ ] Multiple documents can be associated with the correct user and
    plan, if supported by the prototype.
-   [ ] Duplicate, outdated, incomplete, unreadable, or low-quality
    documents are identified or flagged where feasible.
-   [ ] Users can tell which document(s) have been uploaded and
    processed.
-   [ ] Uploaded files are stored and accessed securely, consistent with
    the prototype's deployment and data handling.

## 2. Phase 1 --- Policy-Grounded AI Answers

-   [ ] The AI uses the user's uploaded document(s) as evidence for
    policy-specific answers.
-   [ ] Answers are grounded in retrieved source text rather than
    generic model knowledge alone.
-   [ ] Answers cite the source document and page or another precise
    location where possible.
-   [ ] Citations actually support the answer and point to the correct
    location.
-   [ ] The system explains relevant coverage conditions and limitations
    when present.
-   [ ] Exclusions, exceptions, benefit caps, and limits are identified
    when present.
-   [ ] Deductibles, copays, coinsurance, and out-of-pocket limits are
    interpreted correctly when documented.
-   [ ] Referral and prior authorization language is identified when
    documented.
-   [ ] In-network and out-of-network distinctions are explained when
    documented.
-   [ ] Conflicting provisions across uploaded documents are surfaced
    rather than silently reconciled.
-   [ ] Missing information is explicitly identified.
-   [ ] The AI does not invent benefits, exclusions, rules, amounts, or
    policy language.
-   [ ] The answer distinguishes what the document explicitly states
    from the AI's explanation or inference.
-   [ ] The AI communicates uncertainty when the evidence is incomplete,
    ambiguous, conflicting, or absent.
-   [ ] The AI asks for clarification when important details (such as
    plan, service, or document version) are missing.
-   [ ] The AI can state that the uploaded documents alone are
    insufficient to answer a question.
-   [ ] Uploaded content is treated as untrusted evidence, not as
    instructions to the AI.

## 3. Phase 1 --- Patient Chat and Usability

-   [ ] Users can ask natural-language questions about their uploaded
    insurance documents.
-   [ ] Explanations are clear, concise, and understandable to
    non-experts.
-   [ ] Answers use the correct uploaded document and plan context.
-   [ ] Follow-up questions retain relevant conversation context without
    mixing up unrelated plans or users.
-   [ ] Users can ask about benefits, exclusions, limits, cost-sharing,
    referrals, and authorization language in their documents.
-   [ ] Answers explain practical next steps when appropriate, including
    what should be confirmed with the insurer or provider.
-   [ ] Users can inspect the source supporting an answer.
-   [ ] The chat handles unsupported questions without fabricating
    answers.
-   [ ] Users can access their uploaded documents and relevant prior
    results.
-   [ ] The interface makes clear that a document explanation is not a
    guarantee of coverage, authorization, or final claim payment.

## 4. Cross-Phase --- Safe and Accurate Coverage Interpretation

-   [ ] The product distinguishes a benefit described in a document from
    confirmation of the member's current eligibility and benefits.
-   [ ] The product distinguishes coverage from medical necessity.
-   [ ] The product distinguishes an authorization requirement from an
    authorization decision or approval.
-   [ ] The product distinguishes authorization approval from final
    claim payment.
-   [ ] The product does not imply that a covered service is
    automatically approved or payable.
-   [ ] Cost estimates are only provided when enough relevant
    information is available, and assumptions are explained.
-   [ ] The product flags when current eligibility, benefits, network
    participation, or authorization status have not been verified.
-   [ ] The product avoids unsupported guarantees about coverage,
    patient costs, or approval.
-   [ ] Answers distinguish plan-specific evidence from general
    explanations.
-   [ ] The product clearly states the limits of a Phase 1 answer when
    only uploaded documents are available.

## 5. Phase 2 --- External Insurer and Regulatory Sources (Future Scope)

Assess these as **future requirements and architecture readiness**, not
as Phase 1 failures if external-source retrieval is not yet in scope.

-   [ ] The planned source strategy identifies relevant insurer
    websites, payer policy resources, and official regulatory sources
    such as CMS.
-   [ ] Each source is classified by authority and purpose (for example,
    member plan document, payer medical/authorization policy, or general
    regulation/guidance).
-   [ ] The design distinguishes general CMS or regulatory information
    from insurer-specific rules and member-specific plan terms.
-   [ ] The design defines how the correct payer, plan,
    service/procedure, and applicable jurisdiction will be identified.
-   [ ] External content can be retrieved from documented, permitted
    sources or approved integrations.
-   [ ] Source URL/title, retrieval date, effective date where
    available, and relevant excerpt are retained.
-   [ ] Potentially stale, superseded, or future-effective information
    can be flagged.
-   [ ] Conflicts between uploaded documents and external sources are
    surfaced, with the conflict explained rather than silently resolved.
-   [ ] The system can identify when an uploaded document does not
    contain the applicable authorization or medical-necessity criteria.
-   [ ] The system does not claim current eligibility, benefits, network
    status, or authorization status unless those facts are verified
    through an appropriate source.
-   [ ] If sources cannot establish an answer confidently, the system
    provides a clear verification path.
-   [ ] The plan accounts for source changes, broken links, access
    restrictions, and monitoring/maintenance.
-   [ ] The plan considers approved APIs or integrations where
    appropriate rather than relying exclusively on web scraping.
-   [ ] External-source answers retain citations and distinguish source
    facts from system interpretation.

## 6. Phase 3 --- Provider Authorization Readiness (Future Scope)

Assess as future requirements unless provider workflows are already part
of the prototype.

-   [ ] Provider users can identify a planned service, procedure, test,
    or treatment.
-   [ ] The workflow captures the relevant payer and plan information.
-   [ ] The workflow captures necessary service details, such as
    procedure/code, diagnosis, provider/facility, and place of service,
    when relevant.
-   [ ] The system identifies whether prior authorization appears to be
    required, with source and verification status.
-   [ ] Applicable medical-necessity criteria are identified when
    authoritative, current information is available.
-   [ ] Required clinical records and supporting documentation are
    identified.
-   [ ] Missing information and documentation gaps are flagged.
-   [ ] Referral, network, and other prerequisites are surfaced when
    relevant.
-   [ ] The system generates an actionable authorization-readiness
    checklist.
-   [ ] Staff can review and correct AI-generated findings.
-   [ ] A draft preparation packet can be generated where supported.
-   [ ] Verified requirements are distinguished from items that still
    need confirmation.
-   [ ] The system does not claim that authorization has been obtained
    when it has not.
-   [ ] Final submission and other consequential actions require
    appropriate human review and authorization.
-   [ ] The workflow records case-level time spent, missing information,
    and outcome data where available.
-   [ ] Authorization denials are distinguished from claim denials in
    reporting.

## 7. Cross-Phase --- Accounts, Access, and Data Separation

-   [ ] Each user's documents and conversation data are associated with
    the correct account and plan.
-   [ ] Users can access only data they are authorized to see.
-   [ ] Patient information is not exposed to other patients.
-   [ ] If provider access is supported, access to patient information
    follows appropriate authorization and consent rules.
-   [ ] User roles and permissions are enforced by the backend, not
    merely hidden in the UI.
-   [ ] Authentication, session management, and account recovery work
    correctly where implemented.
-   [ ] Relevant actions are logged and attributable to the correct user
    where needed.
-   [ ] Any planned patient/provider sharing model defines who can share
    what, under which permissions, and how access can be revoked.

## 8. Cross-Phase --- Privacy, Security, and Reliability

-   [ ] Data is encrypted in transit.
-   [ ] Stored sensitive data is protected appropriately for the
    deployment.
-   [ ] File access controls are enforced.
-   [ ] Data retention and deletion behavior is defined and tested.
-   [ ] Sensitive information is not unnecessarily exposed in logs or
    error messages.
-   [ ] Uploaded documents cannot override system instructions or
    trigger unsafe tool behavior through prompt injection.
-   [ ] AI and document-processing failures are handled safely.
-   [ ] Appropriate audit logs are available for the product's risk
    level.
-   [ ] Applicable HIPAA and other privacy/security obligations have
    been assessed for the actual business model, data flows, and
    customers.
-   [ ] Business associate agreements are in place where required before
    relevant PHI handling begins.
-   [ ] The product does not claim HIPAA compliance or other
    certification without supporting evidence.
-   [ ] Prototype testing uses appropriately authorized or de-identified
    documents and data.
-   [ ] The product has a plan for incident response and secure handling
    of exposed or misrouted data.

## 9. Cross-Phase --- Testing and Quality Assurance

-   [ ] Tests cover upload, parsing, OCR, and extraction.
-   [ ] Tests cover correct document retrieval and source citations.
-   [ ] Tests cover ambiguous questions and insufficient evidence.
-   [ ] Tests cover exclusions, exceptions, benefit limits, and
    conditional language.
-   [ ] Tests cover prior authorization and referral language.
-   [ ] Tests cover conflicting, duplicate, outdated, or unreadable
    documents.
-   [ ] Tests cover incorrect or unsupported AI claims.
-   [ ] Tests cover data isolation and patient/provider access
    boundaries where applicable.
-   [ ] Tests cover sensitive-data handling and prompt injection.
-   [ ] Outputs are compared against manually verified interpretations
    of source documents.
-   [ ] Evaluation includes difficult cases, not only straightforward
    questions.
-   [ ] Critical failures are recorded with reproducible examples.
-   [ ] Regression tests are run when prompts, models, retrieval,
    parsing, or business rules change.
-   [ ] Performance is measured separately for extraction accuracy,
    answer accuracy, citation accuracy, uncertainty/abstention quality,
    and consistency.
-   [ ] Evaluation results document the test-set size and limitations;
    claims are not based on anecdotal demonstrations alone.

## 10. Business and Pilot Readiness

-   [ ] The Phase 1 objective is explicitly defined as validating
    document understanding, grounded answers, citations, and uncertainty
    handling.
-   [ ] The initial target user and intended use are defined.
-   [ ] A representative test set of insurance documents and questions
    is available with answers checked against source material.
-   [ ] A threshold for acceptable performance is defined before
    evaluating results.
-   [ ] The team distinguishes technical validation of Phase 1 from
    validation of customer demand and the broader business model.
-   [ ] Potential provider customers are interviewed about real recent
    cases and current workflows.
-   [ ] The most painful workflow, initial specialty, and initial
    payer/procedure scope are selected based on evidence.
-   [ ] Phase 2 sources are prioritized based on the validated use case
    rather than added indiscriminately.
-   [ ] The product can measure relevant outcomes in a future pilot,
    such as staff time per case, missing information identified,
    completeness, and outcomes where available.
-   [ ] The product is not marketed as guaranteeing approvals, coverage,
    payment, or eliminating all denials.
-   [ ] Customer willingness to pay and measurable value can be tested
    before significant integration investment.

------------------------------------------------------------------------

## Required Audit Output

### A. Overall status

Report results separately for: 1. **Phase 1 --- current prototype** 2.
**Cross-phase foundations** 3. **Phase 2 --- external-source readiness**
4. **Phase 3 --- provider-workflow readiness**

For each group, report assessed items and counts/percentages of PASS,
PARTIAL, FAIL, N/A, and UNVERIFIED. Do not mix future-phase readiness
observations with Phase 1 implementation scores.

Also provide: - The five most serious gaps or risks. - Whether the
current build is suitable for an internal demo, a supervised prototype
test, a supervised pilot, or production use. - The evidence supporting
that recommendation.

### B. Gap register

For each PARTIAL, FAIL, or UNVERIFIED item, provide: - Phase and
checklist section/item. - Evidence from the existing implementation. -
What is missing or needs verification. - User and business impact. -
Recommended fix. - Priority: **P0 critical**, **P1 essential**, **P2
important**, or **P3 later**.

### C. Prioritized action plan

Group recommendations into: 1. **P0** --- Security/data isolation
failures, fabricated or materially misleading answers, unsupported
claims, and other critical risks. 2. **P1** --- Phase 1 document
extraction, grounded answers, citations, uncertainty handling, and
evaluation essentials. 3. **P2** --- Usability improvements and
preparation for validated Phase 2 sources or Phase 3 workflows. 4.
**P3** --- Advanced integrations and automation not needed to validate
the current prototype.

### D. Final recommendation

Recommend the smallest set of changes needed to validate Phase 1 with
realistic insurance documents and questions. Identify which future
requirements should be designed for now, which should wait, and what
evidence should trigger progression to the next phase.

**Audit only. Do not implement changes, rewrite working features, or
assume a planned feature is missing from the current phase. Base
findings on evidence and explicitly disclose anything that could not be
verified.**
