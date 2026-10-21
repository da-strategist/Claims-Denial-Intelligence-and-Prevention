# Product Audit Results — Patient Plan RAG

Audit of commit `7f9063e` (2026-10-21) against `Product_Audit_Checklist.md`.
Audit only: no code was changed. Evidence comes from the code, the test
suites (375 backend, 96 frontend), the multi-policy evaluation
(`python -m backend.app.tests.policy_eval`), end-to-end scripts against a
scratch backend, and a browser walkthrough of all four account types. One
probe was run for this audit: an image-only (scanned-style) PDF processed in
a temporary folder.

Important context: all documents used so far are **four synthetic policies**
written for this project. Nothing has been tested on real insurer documents.
Live mode (Claude) is built but **has never been run against the real API**;
every result below is for the default demo mode unless stated.

Status key: PASS · PARTIAL · FAIL · N/A · UNVERIFIED.

---

## A. Overall status

| Group | Items | PASS | PARTIAL | FAIL | N/A | UNVERIFIED |
|---|---|---|---|---|---|---|
| **Phase 1 — current prototype** (§1–3) | 39 | 22 (56%) | 14 (36%) | 3 (8%) | 0 | 0 |
| **Cross-phase foundations** (§4, 7, 8, 9, 10) | 57 | 21 (37%) | 26 (46%) | 3 (5%) | 3 (5%) | 4 (7%) |
| **Phase 2 — external-source readiness** (§5) | 15 | 1 | 4 | 0 | 10 | 0 |
| **Phase 3 — provider-workflow readiness** (§6) | 16 | 3 | 8 | 0 | 5 | 0 |

Phase 2 and 3 rows are readiness observations, not Phase 1 scores. Phase 3
is partly built already (provider prior-auth workflow), so its items were
assessed against what exists.

### Five most serious gaps or risks

1. **Scanned / unreadable PDFs fail silently** (§1.5, 1.10). Verified: an
   image-only PDF is stored as `completed` with 0 chunks and no warning;
   every question then gets "insufficient evidence" with no explanation.
   Real member documents are often scanned.
2. **Answer accuracy is not established for real documents** (§2.4, 9.10,
   10.3). 4 synthetic policies, 38 questions, ground truth written by the
   same author as the fixes. The visual check found a starter question
   answered from the wrong section (since fixed), which the eval did not
   catch. Demo answers quote passages and sometimes quote a section's
   lead-in rather than the list that answers the question.
3. **No ambiguity or conflict handling** (§2.10, 2.15, 9.6). With several
   policies in scope and no plan named, all are searched together; the app
   never asks which plan is meant, never detects contradictory provisions,
   and does not flag duplicate uploads.
4. **Live AI mode is untested against the real model** (§2.13, 3.2, 8.6).
   Fencing, citation verification and refusal handling are tested with a
   fake client only. Plain-language explanations (vs. verbatim quotes) depend
   on live mode.
5. **Deployment security and compliance groundwork is missing** (§8.1, 8.2,
   8.9, 8.13, 7.6). No HTTPS configuration, no encryption at rest, sessions
   in memory, no HIPAA assessment, no incident-response plan, no
   self-service account recovery or identity verification. Not blocking for
   a demo with synthetic data; blocking for any real data.

No data-isolation failure, fabricated answer, or coverage guarantee was
found.

### Suitability

| Use | Suitable? |
|---|---|
| Internal demo | **Yes** |
| Supervised prototype test (synthetic or de-identified documents) | **Yes**, with the scanned-PDF and multi-plan caveats explained to testers |
| Supervised pilot with real users / real PHI | **No** — needs HTTPS, encryption at rest, HIPAA assessment and BAA, real-document evaluation, scanned-PDF handling |
| Production | **No** |

Evidence: access rules enforced server-side on every route (structural test
covers all 61 routes; per-role isolation tests in `test_access.py`,
`test_hospital.py`, `test_shared_patients.py`, `test_platform_admin.py`);
hash-chained audit log; disclaimers on every page and API response; eval
37/38 cited section and answer text on synthetic policies; but the gaps
above.

---

## Item-by-item results

### §1 Phase 1 — Document upload and processing

| # | Item | Status | Evidence |
|---|---|---|---|
| 1.1 | Users can upload documents | PASS | `POST /api/policies/upload`; individuals, provider staff (to a patient), admin (samples); tests + browser |
| 1.2 | File types, size limits, constraints | PASS | `%PDF-` magic check, `MAX_UPLOAD_MB`, sanitised names, `accept=".pdf"`, 10/min upload rate limit (`test_input_limits.py`) |
| 1.3 | Understandable failure messages | PARTIAL | Validation errors are clear ("Only PDF files are accepted", "File is empty"); a processing failure or empty extraction still returns 200 "Processed 0 text chunks" |
| 1.4 | Text PDFs parsed correctly | PASS | pdfplumber with font-based headings; 4 deliberately different layouts; metadata 20/20, summary 22/22 (synthetic only) |
| 1.5 | Scanned documents: OCR or flagged unsupported | **FAIL** | Probe: image-only PDF → `status: completed, chunks: 0`, no warning; no OCR |
| 1.6 | Sections extracted without losing conditions, tables, footnotes | PARTIAL | Section-aware chunking; table rows handled as line labels; no table-structure or footnote handling; only synthetic layouts tested |
| 1.7 | Document name, page, source text kept for citations | PASS | `SourceCitation` (document_name, page_number, section, excerpt); chunk viewer |
| 1.8 | Plan identifiers extracted or flagged unavailable | PASS | insurer, plan, plan ID, dates extracted verbatim; missing shown ("Insurer not stated", sample health "missing: plan id") |
| 1.9 | Multiple documents per user / plan | PASS | Individuals hold several; provider documents per patient record; insurance grouped by insurer |
| 1.10 | Duplicate, outdated, incomplete, unreadable flagged | PARTIAL | Ended plans flagged (badge, `coverage_status`); duplicate uploads not detected; unreadable not flagged (1.5) |
| 1.11 | Users can see what was uploaded and processed | PASS | Policy lists with pages, chunks, status; patient insurance table |
| 1.12 | Files stored and accessed securely | PARTIAL | No direct file serving, access checks on every read, records written 0600; no encryption at rest; local disk |

### §2 Phase 1 — Policy-grounded AI answers

| # | Item | Status | Evidence |
|---|---|---|---|
| 2.1 | Uses uploaded documents as evidence | PASS | Retrieval limited to the user's documents (`Access.default_search_ids`) |
| 2.2 | Grounded in retrieved text | PASS | Demo answers are verbatim quotes; live mode sends passages only and verifies citations (fake-client tests) |
| 2.3 | Cites document and page | PASS | Every citation has document, page, section |
| 2.4 | Citations support the answer and point correctly | PARTIAL | Eval: cited section 37/38, answer text 37/38 (synthetic, same author); visual check found a wrong-section answer (fixed in `7f9063e`) |
| 2.5 | Explains coverage conditions and limits | PARTIAL | Conditions surface as quoted passages and in Coverage Check; demo mode does not synthesise an explanation |
| 2.6 | Exclusions, exceptions, caps, limits identified | PARTIAL | Coverage classification 15/15 and summary fields 22/22 on the eval; chat depends on retrieval ranking |
| 2.7 | Deductibles, copays, coinsurance, OOP correct | PARTIAL | Quoted verbatim (plan at a glance, summary); no interpretation or arithmetic; known gap: "What does coinsurance mean?" ranks the definition second |
| 2.8 | Referral and prior-auth language identified | PASS | Per-policy next-step tests; approval section found under any of its names (`adapt_vocabulary`, tests for all 4 policies) |
| 2.9 | In- vs out-of-network explained | PARTIAL | Passages quoted when retrieved; Coverage Check has `network_notes`; no dedicated eval questions |
| 2.10 | Conflicting provisions across documents surfaced | **FAIL** | No conflict detection; multi-document answers quote both without comparison |
| 2.11 | Missing information identified | PARTIAL | "Insufficient evidence" answers; Coverage Check `missing_information`; chat does not name what is missing |
| 2.12 | Does not invent benefits, rules, amounts | PASS | Demo never generates text beyond quotes; live drops fabricated or out-of-range citations (`test_live_mode.py`) |
| 2.13 | Distinguishes explicit text from inference | PARTIAL | Citations labelled supported / interpreted; answer footer says it is an interpretation; live answer text not separated |
| 2.14 | Communicates uncertainty | PARTIAL | Confidence levels and minimum-coverage threshold; ambiguity and conflicts not detected |
| 2.15 | Asks for clarification when plan/service/version missing | **FAIL** | Never asks; searches every policy in scope (only a plan named in the question narrows it) |
| 2.16 | Can say documents are insufficient | PASS | `no_evidence` message with next steps; tests |
| 2.17 | Uploaded content treated as untrusted evidence | PASS | Demo (default) never sends documents to a model; live fences and escapes passages, system prompt says "not instructions" (fake-client tests; see 8.6) |

### §3 Phase 1 — Patient chat and usability

| # | Item | Status | Evidence |
|---|---|---|---|
| 3.1 | Natural-language questions | PASS | Chat for individuals and staff |
| 3.2 | Clear for non-experts | PARTIAL | Plan at a glance and next steps help; demo answers are policy quotes, not plain-language explanations |
| 3.3 | Correct document and plan context | PASS | Policy picker, patient scope for staff, named-plan focus (`test_named_plan.py`) |
| 3.4 | Follow-ups keep context without mixing plans/users | PASS | Server-side conversations owned by one user, locked to one policy/patient; known quality gap: "How often can I get them?" (Riverbend) |
| 3.5 | Benefits, exclusions, limits, cost-sharing, referrals, auth | PASS | Starter questions and eval cover each |
| 3.6 | Practical next steps incl. what to confirm | PASS | Cited next steps (audience-specific); "verify with plan administrator" on every answer |
| 3.7 | User can inspect sources | PASS | Citation excerpts; policy viewer with chunks and summary |
| 3.8 | Unsupported questions not fabricated | PASS | Low-coverage questions get "insufficient evidence" |
| 3.9 | Access documents and prior results | PARTIAL | Documents yes; chats kept ≤ 1 h in memory, no history; saved checklists only for providers |
| 3.10 | Not a guarantee of coverage/authorization/payment | PASS | Disclaimer on every page, every API response (`X-Disclaimer`), and in answers |

### §4 Cross-phase — Safe coverage interpretation

| # | Item | Status | Evidence |
|---|---|---|---|
| 4.1 | Document benefit vs current eligibility | PARTIAL | General disclaimer only; answers don't state eligibility is unverified |
| 4.2 | Coverage vs medical necessity | PARTIAL | Prior-auth checklist mentions medical necessity; chat and Coverage Check don't distinguish |
| 4.3 | Auth requirement vs auth decision | PARTIAL | Wording says "request prior authorization"; no explicit statement that a requirement isn't a decision |
| 4.4 | Auth approval vs claim payment | PARTIAL | Not stated explicitly |
| 4.5 | Covered ≠ automatically approved or payable | PARTIAL | Prior-auth language makes classification "conditional"; a "covered" label has no approval/payment caveat beside it |
| 4.6 | Cost estimates only with enough information | N/A | The product makes no cost estimates |
| 4.7 | Flags unverified eligibility, network, auth status | PARTIAL | Disclaimer only |
| 4.8 | No unsupported guarantees | PASS | `test_next_steps_never_promise_coverage`; disclaimers; landing copy |
| 4.9 | Plan-specific evidence vs general explanation | PARTIAL | Demo is plan-specific only; live may mix, unlabelled |
| 4.10 | States limits of a Phase 1 answer | PASS | Footer: based on cited passages, may miss conditions, verify with the plan |

### §5 Phase 2 — External sources (readiness)

| # | Item | Status | Observation |
|---|---|---|---|
| 5.1–5.5 | Source strategy, authority classes, payer/plan/jurisdiction identification, permitted retrieval | N/A | Not started; no design document. `document_type` and `is_synthetic` fields exist in the registry and could carry source class |
| 5.6 | URL/title, retrieval date, effective date, excerpt kept | PARTIAL | Citation keeps title, page, excerpt; effective dates extracted; no URL or retrieval date fields |
| 5.7 | Stale/superseded/future information flagged | PARTIAL | Ended/upcoming status from document dates exists and could extend to external sources |
| 5.8 | Conflicts between uploads and external sources | N/A | Depends on 2.10, which is missing |
| 5.9 | Detects that uploads lack authorization/medical-necessity criteria | PARTIAL | Insufficient-evidence path exists; not specific to criteria |
| 5.10 | No claims of verified eligibility/network/auth status | PASS | The product makes no such claims |
| 5.11 | Clear verification path when sources can't answer | PARTIAL | Generic "contact the plan administrator" |
| 5.12–5.15 | Source maintenance, APIs vs scraping, citations for external answers | N/A | Not started. The "no live external integrations" constraint in CLAUDE.md applies |

### §6 Phase 3 — Provider authorization readiness

| # | Item | Status | Evidence |
|---|---|---|---|
| 6.1 | Identify planned service | PASS | Prior Auth page: service/procedure |
| 6.2 | Payer and plan captured | PARTIAL | From the patient's policy metadata; no member ID or payer identifiers |
| 6.3 | Code, diagnosis, provider/facility, place of service | PARTIAL | CPT/HCPCS and diagnosis code fields; no ordering provider, facility or place of service |
| 6.4 | Prior auth appears required, with source and verification status | PARTIAL | Coverage Check `prior_auth_required` with citations; no verification-status field |
| 6.5 | Medical-necessity criteria | N/A | Needs Phase 2 sources |
| 6.6 | Required clinical records identified | PARTIAL | Standard checklist items plus policy-derived items |
| 6.7 | Missing information flagged | PARTIAL | Coverage Check `missing_information`; checklist items not tied to patient records |
| 6.8 | Referral, network, prerequisites | PARTIAL | Referral detection and staff next steps; network notes only when retrieved |
| 6.9 | Actionable readiness checklist | PASS | Generate, save on the patient record, tick off (`test_hospital.py`) |
| 6.10 | Staff can review and correct findings | PARTIAL | Items can be ticked; text can't be edited and items can't be added |
| 6.11 | Draft preparation packet | N/A | Not built |
| 6.12 | Verified vs needs-confirmation items | PARTIAL | Items labelled policy-sourced vs suggested |
| 6.13 | Never claims authorization obtained | PASS | No such state exists |
| 6.14 | Human review before submission | N/A | No submission feature |
| 6.15 | Case time, missing info, outcome data | N/A | Not built (audit timestamps only) |
| 6.16 | Auth denials vs claim denials in reporting | N/A | Not built |

### §7 Cross-phase — Accounts, access, data separation

| # | Item | Status | Evidence |
|---|---|---|---|
| 7.1 | Documents and conversations tied to the right account | PASS | `owner` / `org_id` + `patient_id` on documents; conversations owned |
| 7.2 | Users see only authorized data | PASS | `Access` class; inaccessible items return 404; route-protection test covers all 61 routes |
| 7.3 | Patients never see other patients' data | PASS | `test_access.py` cross-user tests |
| 7.4 | Provider access follows authorization and consent | PARTIAL | Explicit per-policy sharing, revocable at once; connection shows name/email only; providers approved by admin. No identity verification of individuals; consent wording not reviewed |
| 7.5 | Roles enforced in the backend | PASS | `require(Permission.X)` on every route |
| 7.6 | Authentication, sessions, account recovery | PARTIAL | scrypt, HttpOnly cookies, throttling, sign-out everywhere; no self-service password reset or email verification |
| 7.7 | Actions logged and attributable | PASS | Hash-chained audit log; plain-words labels; sign-out attributed (`test_audit.py`) |
| 7.8 | Sharing model defined | PASS | Who shares what, revocation, provider records: CLAUDE.md + `test_shared_patients.py`, `test_connections.py` |

### §8 Cross-phase — Privacy, security, reliability

| # | Item | Status | Evidence |
|---|---|---|---|
| 8.1 | Encryption in transit | PARTIAL | `COOKIE_SECURE` option exists; app runs over plain HTTP locally; no HTTPS setup |
| 8.2 | Stored sensitive data protected | PARTIAL | Hashed passwords, 0600 files; no encryption at rest |
| 8.3 | File access controls enforced | PASS | PDFs never served directly; every read checked |
| 8.4 | Retention and deletion defined and tested | PARTIAL | Account deletion tested; chats ≤ 1 h; audit-log retention undefined; emails kept in the audit log |
| 8.5 | No sensitive data in logs or errors | PARTIAL | Audit log has no content; server logs only exception types; uvicorn access logs contain emails in admin URLs |
| 8.6 | Prompt injection can't override instructions | PARTIAL | Fenced, escaped passages + system prompt; tested only with a fake client |
| 8.7 | AI and document failures handled safely | PARTIAL | Live errors fall back to demo answers; document failures are silent (1.3, 1.5) |
| 8.8 | Audit logs appropriate to risk | PASS | Every request logged, tamper check in the UI, security events |
| 8.9 | HIPAA obligations assessed | **FAIL** | Not done; only a "before real use" list in CLAUDE.md |
| 8.10 | BAAs before PHI handling | N/A | No PHI handled yet; BAA with Anthropic listed as required before live mode with real data |
| 8.11 | No unsupported HIPAA/certification claims | PASS | No such claim anywhere in code or UI (searched) |
| 8.12 | Testing uses authorized/de-identified data | PASS | Synthetic only (project constraint) |
| 8.13 | Incident response plan | **FAIL** | None |

### §9 Cross-phase — Testing and QA

| # | Item | Status | Evidence |
|---|---|---|---|
| 9.1 | Upload, parsing, OCR, extraction tests | PARTIAL | Upload, parsing, extraction tested; no OCR or scanned-PDF test |
| 9.2 | Retrieval and citation tests | PASS | `test_retrieval.py`, eval, `test_live_mode.py` |
| 9.3 | Ambiguous questions and insufficient evidence | PARTIAL | Insufficient evidence tested; no ambiguity tests |
| 9.4 | Exclusions, limits, conditional language | PASS | Eval coverage classification; `test_suggestions.py` |
| 9.5 | Prior auth and referral | PASS | Per-policy next-step tests; approval-section tests |
| 9.6 | Conflicting, duplicate, outdated, unreadable documents | **FAIL** | Only expired-plan status is tested |
| 9.7 | Incorrect or unsupported AI claims | PASS | Fabricated-citation and never-promise tests |
| 9.8 | Data isolation and access boundaries | PASS | Extensive per-role tests |
| 9.9 | Sensitive data and prompt injection | PASS | Redaction and fencing tests (fake client) |
| 9.10 | Compared against manually verified interpretations | PARTIAL | Ground truth hand-written from synthetic documents by the same author |
| 9.11 | Difficult cases included | PARTIAL | Some (follow-ups, vocabulary); limited |
| 9.12 | Critical failures recorded reproducibly | PARTIAL | Known gaps in CLAUDE.md; no defect log |
| 9.13 | Regression tests on every change | PARTIAL | Eval ratchet runs in pytest; no CI, so it depends on someone running it |
| 9.14 | Separate metrics (extraction, answer, citation, abstention, consistency) | PARTIAL | Extraction, answer text and citation measured; abstention quality and consistency not |
| 9.15 | Test-set size and limitations documented | PASS | CLAUDE.md states 38 questions, same author, "regression guards, not accuracy claims" |

### §10 Business and pilot readiness

| # | Item | Status | Evidence |
|---|---|---|---|
| 10.1 | Phase 1 objective defined as validation | PARTIAL | CLAUDE.md defines a prototype; not framed as a validation goal with criteria |
| 10.2 | Target user and intended use defined | PASS | Individuals and providers, documented |
| 10.3 | Representative test set checked against sources | PARTIAL | 4 synthetic policies, 38 questions; not representative of real documents |
| 10.4 | Performance threshold defined before evaluating | PARTIAL | Ratchet thresholds were set from results, not in advance |
| 10.5 | Technical vs demand validation distinguished | UNVERIFIED | Nothing in the repository |
| 10.6 | Provider interviews | UNVERIFIED | Nothing in the repository |
| 10.7 | Workflow, specialty, payer scope chosen on evidence | UNVERIFIED | Scope is broad (all provider categories) |
| 10.8 | Phase 2 sources prioritised by use case | N/A | Phase 2 not started |
| 10.9 | Pilot outcomes measurable | PARTIAL | Activity counts on the dashboard; no time-per-case or completeness metrics |
| 10.10 | Not marketed as guaranteeing outcomes | PASS | Disclaimers and landing copy |
| 10.11 | Willingness to pay testable | UNVERIFIED | Nothing in the repository |

---

## B. Gap register

Priorities: P0 critical · P1 essential · P2 important · P3 later.

| Item | Evidence | Missing / to verify | Impact | Recommended fix | Pri |
|---|---|---|---|---|---|
| 1.5 Scanned PDFs | Probe: completed, 0 chunks | Detection + message; OCR option | Users with scanned plans get unexplained "no evidence" answers | Mark 0-text uploads `failed` with a clear message; add OCR later (e.g. Tesseract) behind a flag | P1 |
| 1.3 Failure messages | Upload returns 200 on empty extraction | Error status and wording | Silent failures | Return 422 with "no readable text" | P1 |
| 1.10 Duplicates / unreadable | Same PDF twice = two documents | Content-hash duplicate check | Duplicate citations, confusion | Warn on identical content hash per owner | P2 |
| 1.6 Tables / footnotes | Line-label handling only | Table structure, footnotes | Missed conditions in real SBC tables | Evaluate pdfplumber table extraction on real SBCs | P1 |
| 1.12 / 8.2 Storage security | 0600 files, no encryption | Encryption at rest | Exposure if disk is copied | Reuse claim_validation_tool's encryption pattern | P0 before real data |
| 2.4 / 9.10 / 10.3 Accuracy evidence | 38 synthetic questions | Real, de-identified documents; independent ground truth | Reliability unknown | Build a 50–100 question set from 5–10 real de-identified plans, answers checked by someone else | P1 |
| 2.15 Clarification | Searches all plans | Ask which plan when several match | Mixed-plan answers | When results span plans and none is named, ask or answer per plan | P1 |
| 2.10 / 9.6 Conflicts | None | Detect differing amounts/rules across plans | Silently mixed information | Group answers by document; flag differing values for the same field | P1 |
| 2.13 / 4.9 Explicit vs inference | Citation labels only | Clear separation in the answer | Users may read interpretation as policy text | "The policy says" (quotes) vs "What this likely means" sections | P1 |
| 2.11 / 2.14 Missing info, uncertainty | Generic insufficient message | Name what's missing; ambiguity signals | Less useful abstentions | Return missing fields from Coverage Check in chat | P2 |
| 2.5 / 2.6 / 2.7 / 2.9 / 3.2 Explanations | Demo quotes | Plain-language synthesis | Hard for non-experts | Run live mode (after the live test and BAA where needed) | P1 |
| Live mode untested (2.13, 8.6) | Fake client only | Real API run | Unknown real behaviour | Run the planned live check with injection test documents | P1 |
| 3.9 Prior results | Chats ≤ 1 h | Saved answers | Users can't revisit answers | Optional "save this answer" per user | P2 |
| 4.1–4.5, 4.7 Coverage distinctions | Disclaimer only | Explicit statements | Users may equate "covered" with "approved/paid" | Short fixed note on coverage/prior-auth answers: requirement ≠ approval ≠ payment; eligibility not verified | P1 |
| 7.4 Consent / identity | No identity verification | Verification, reviewed consent wording | Wrong person could share/receive | Identity check before sharing; compliance-reviewed consent text | P0 before real data |
| 7.6 Account recovery | Admin resets only | Self-service reset, email verification | Support burden, account takeover risk | Email service + reset flow | P1 before pilot |
| 8.1 HTTPS | Plain HTTP locally | TLS in deployment | Credentials and data in clear | TLS at the proxy, `COOKIE_SECURE=true` | P0 before real data |
| 8.4 Retention | Audit retention undefined | Policy + tests | Unbounded personal data | Define retention; pseudonymous audit IDs | P1 |
| 8.5 Logs | Emails in uvicorn access logs | Log scrubbing | PII in server logs | Disable/scrub access logs | P2 |
| 8.7 Document failures | Silent | See 1.3 / 1.5 | — | — | P1 |
| 8.9 HIPAA assessment | None | Assessment of data flows and roles | Legal exposure | Assess before any pilot with PHI | P0 before real data |
| 8.13 Incident response | None | Plan | Slow, unsafe response | Short runbook: detect, contain, notify, review | P1 |
| 9.1 OCR tests | None | Tests for scanned/empty PDFs | Regressions | Add with the 1.5 fix | P1 |
| 9.3 Ambiguity tests | None | Test cases | — | Add with 2.15 | P2 |
| 9.11 / 9.12 Hard cases, defect log | Limited | Defect log with repro | Repeated regressions | Record each failure as an eval case | P2 |
| 9.13 CI | Manual | CI running pytest + vitest + eval | Unnoticed regressions | GitHub Actions workflow | P2 |
| 9.14 Metrics | No abstention/consistency metrics | Measure both | Blind spots | Add "should abstain" questions and repeat-run checks | P2 |
| 10.1 / 10.4 Objective and thresholds | Not defined | Written goal and pass thresholds | Can't decide when Phase 1 is done | Write before the real-document evaluation | P1 |
| 10.5–10.7, 10.11 Business validation | Not in repo | Interviews, scope, pricing tests | Building without demand evidence | Interview 5–10 provider staff about recent cases | P1 (business) |
| 10.9 Pilot metrics | Activity counts only | Time per case, completeness | Can't show value | Add case timing to checklists in Phase 3 | P3 |
| 6.x Provider workflow gaps (6.2–6.4, 6.6–6.8, 6.10, 6.12) | Partly built | Member ID, facility, place of service, editable items, verification status | Limited usefulness for real prior-auth work | Defer until provider interviews pick the workflow | P2–P3 |
| 5.x Phase 2 readiness | Not started | Source design | — | Design note only (see D) | P3 |

---

## C. Prioritized action plan

**P0 — before any real data (not needed for a synthetic demo)**
- HTTPS and secure cookies; encryption at rest; HIPAA assessment and BAA
  plan; identity verification and reviewed consent wording for sharing.
- No P0 issue was found in data isolation, fabricated answers or guarantees.

**P1 — to validate Phase 1**
1. Detect unreadable/scanned PDFs and tell the user (then OCR).
2. Write the Phase 1 objective and pass thresholds; build a real,
   de-identified test set with independently checked answers.
3. Ask which plan when several match; flag conflicting provisions.
4. Separate quoted policy text from explanation in answers; add the fixed
   requirement ≠ approval ≠ payment / eligibility-not-verified note.
5. Run the live-mode check (including injection test documents); use live
   explanations if they pass.
6. Account recovery, retention policy, incident runbook (before a pilot).

**P2 — usability and preparation**
- Duplicate detection, saved answers, missing-information detail, log
  scrubbing, CI, abstention/consistency metrics, defect log, table
  extraction review.

**P3 — later**
- External sources (Phase 2), draft packets, submission workflows, case
  timing and outcome reporting (Phase 3).

---

## D. Final recommendation

**Smallest set of changes to validate Phase 1 with realistic documents:**
1. Unreadable-PDF detection with a clear message.
2. A written objective and thresholds (for example: cited section ≥ 90%,
   correct abstention ≥ 90%, zero fabricated amounts), then 5–10 real
   de-identified plans with 50–100 independently answered questions,
   including "should abstain" and multi-plan questions.
3. Plan clarification and conflict flagging for multi-document users.
4. Answers that separate "the policy says" from "what this means", plus the
   fixed coverage/approval/payment note.
5. One live-mode run against the evaluation (with permission and cost
   approval) to decide whether demo or live answers go into testing.

**Design now, build later:** a source model with authority class, URL,
retrieval and effective dates (extends today's citation and date fields);
verification status on checklist items; case timing hooks.

**Wait:** external-source retrieval, packets, submissions, outcome
reporting.

**Evidence to move to Phase 2:** Phase 1 thresholds met on real documents;
provider interviews showing that the answers people need are missing from
member documents (e.g. medical-necessity criteria); a chosen specialty and
payer scope.

**Could not be verified in this audit:** real-model (live) behaviour;
performance on real insurer documents; phone-width layout (window would not
resize below ~710px); anything about business validation, which is outside
the repository.
