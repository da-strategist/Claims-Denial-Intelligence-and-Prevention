# Build Phases — ClaustraRCM Claim Validation Tool

> Status key: `[ ]` Pending | `[~]` In Progress | `[x]` Completed

---

## Phase 1: Environment & Project Skeleton
- [x] Create `claim_validation_tool/` directory structure (backend/, frontend/)
- [x] Add FastAPI + uvicorn to pyproject.toml dependencies
- [x] Scaffold React app with Vite
- [x] Create minimal FastAPI health endpoint
- [x] Create minimal React app that calls backend
- [x] Verify both servers start and communicate
- [x] Create project documentation (README, PROJECT_GUIDE, PHASES)

## Phase 2: Data Layer & Synthetic Claims API
- [x] Create Pydantic models for Claim, Denial, Payer, Provider
- [x] Build synthetic data module (load from CSVs or generate in-memory)
- [x] Create `/api/claims` endpoint (list, search, filter, paginate)
- [x] Create `/api/claims/{id}` endpoint (single claim detail)
- [x] Wire up React to display claims from the API
- [x] Set up Tailwind CSS in the frontend build
- [x] Backend tests for the data layer and claims API (fixture dataset)

## Phase 3: Validation Engine (Backend)
- [x] Create Rule Pydantic model (conditions, scope, severity, category)
- [x] Build validation engine service (evaluate conditions against claims)
- [x] Build risk scoring service
- [x] Create `/api/rules` endpoints (CRUD, plus `/fields` catalog and `/test` for draft rules)
- [x] Create `/api/validate` endpoint (run rules against claims)
- [x] Create default rule set (seed data)
- [x] Engine, risk scorer, and rules/validate API tests

## Phase 4: Claims Workbench (Frontend)
- [x] Build Claims table component with search, filter, sort
- [x] Build expandable row with validation details
- [x] Build status badges (Pass, Warning, Error, AI Fix)
- [x] Connect to validation API
- [x] Add pagination

## Phase 5: Rule Manager & Custom Rule Builder (Frontend)
- [x] Build rule list view with toggle/edit/delete
- [x] Build Rule Builder slide-in panel
- [x] Build Condition Builder (field/operator/value, AND/OR logic)
- [x] Build Test Rule functionality
- [x] Connect to rules API
- [x] Persist rules to `backend/rules.json` (gitignored) so edits survive restarts
- [x] `/api/departments` and per-field operators in `/api/rules/fields` for the builder

## Phase 6: AI Fix Workflow
- [x] Build AI fix suggestion service (backend) — rule-based, behind a swappable `FixSuggester` interface, with citations from reference data
- [x] Create `/api/aifix` endpoint (suggestions, apply, undo corrections)
- [x] Add AI Fix actions to Claims Workbench expanded rows
- [x] Apply fix and re-validate flow — corrections layered over source data in `backend/claim_corrections.json` (gitignored), undoable
- [x] Suggestions tag clarification topics for the Phase 10 assistant ("Ask the assistant" placeholder)
- Deferred: LCD/NCD, MUE, and NCCI checks — the synthetic claim lines aren't generated consistently with those reference tables (checks would flag 20–95% of claims). Revisit with Phase 10 once the data generator is aligned.

## Phase 7: Executive Dashboard
- [x] Create `/api/dashboard` endpoint (KPIs, chart data) — filters by trailing months, payer, department; KPIs compared with the preceding period of equal length
- [x] Build KPI cards component (change vs prior period, colored by whether it's an improvement)
- [x] Build charts (Revenue Trends, Denial Reasons, AR Aging, Claim Validation Status) plus a Payer Performance table
- [x] Connect to dashboard API — validation status for all claims is cached server-side and refreshed when rules or corrections change

## Phase 8: JAB Audit Integration (Conceptual)
- [x] Build workflow diagram component — six steps, marked Live / Needed / Proposed, closing the loop back into Rule Manager
- [x] Build integration architecture cards — ClaustraRCM, JAB Audit, clearinghouse, EHR/PM, contract repository, security & compliance
- [x] Design future API contracts — claim handoff (out), underpayment findings, recovery status, rule suggestions (in). Pydantic models in `models/jab.py`, served by `GET /api/jab/contracts` as field tables, JSON Schema, and validated examples
- Not built: a live underpayment preview. The synthetic allowed amounts aren't generated from contract rates (allowed/expected ranges 0.5–1.9×), so variance figures would be noise. Revisit once the data generator is aligned.

## Phase 9: Polish & Testing
- [x] Backend unit tests (validation engine, risk scorer, AI fix)
- [x] Frontend component testing
- [x] API integration tests
- [x] UI polish and responsive design
- [x] Error handling and loading states
- [x] Final documentation

## Phase 10: RAG Clarification Assistant
Works alongside the rule-based engine: rules handle clear-cut cases; the assistant
answers a billing specialist's clarification questions with cited sources where
rules can't resolve the ambiguity.

Use cases, in priority order:
1. Medical necessity — LCD/NCD coverage for a CPT + ICD-10 combination
2. NCCI / modifiers — PTP edits, modifier eligibility, MUE limits
3. Payer prior authorization rules — requirements, retro-auth, contract terms
4. Appeal wording — draft appeal language from CARC/RARC codes and claim context

Tasks:
- [x] Choose LLM provider, embedding model, and vector store — Claude API (Sonnet 5.5); no embeddings or vector store: the ~370 structured records are looked up by code, plus BM25 keyword search
- [x] Build knowledge base from reference data (`ref_lcd_ncd_policies`, `ref_ncci_ptp_edits`, `ref_mue_limits`, `ref_carc_codes`, `ref_rarc_codes`, `dim_payer_contracts`), plus `dim_payers` and `ref_physician_fee_schedule` — existing tables only; no payer policy documents exist
- [x] Ingestion and chunking pipeline with source metadata for citations — one source per table row, keyed by its codes
- [x] Retrieval service and `/api/assistant` endpoint (question + claim context → answer with citations)
- [x] Data-handling review: what claim/PHI fields may be sent to the LLM
- [x] "Ask the assistant" action on findings flagged as needing clarification (from Phase 6)
- [x] Evaluation set of billing questions to measure answer accuracy and citation quality — 17 cases; retrieval 17/17, MRR 1.00; answer grading needs `ANTHROPIC_API_KEY` and hasn't been run yet

---

## Before going live on real claims

Settings chosen for the synthetic sample data that must change once the tool runs on real,
continuous claims:

- **Overview period.** The Overview opens on *All time* (`DEFAULT_DASHBOARD_MONTHS` in
  `frontend/src/constants.js`), and "Last N months" counts back from the latest service date
  in the data (`_periods` in `backend/app/services/dashboard.py`). That's because the sample
  claims end in December 2025 while claims entered now carry 2026 dates, so one new claim
  would move the window onto mostly empty months. On real data, switch to counting back
  **from today** and open on *Last 12 months*.
- **Sample patient registrations.** The synthetic patients' dates of birth, addresses, and
  member IDs are generated (`backend/app/data/registrations.py`, marked "sample" in the
  form). Real patients' details must come from the hospital's registration system or be
  captured on their first claim; turn off sample generation.
- **837 settings.** Complete `backend/edi_settings.json` (submitter, clearinghouse, billing
  provider with NPI, EIN and ZIP+4, payer IDs), give facilities ZIP+4 addresses, set `mode`
  to `production`, and validate a test file with the clearinghouse first.
- **Prior authorization lists.** Load the hospital's list for each of its main payers on the Users
  page, and agree who keeps them current. Until then, its claims show prior auth as not assessed.
- **Encryption at rest.** Generate a master key (`uv run python -m app.orgs new-master-key`),
  put it in the key service (in `backend/.env` until then) with a backup copy kept
  separately, run `uv run python -m app.orgs encrypt` with the API stopped, and set
  `RCM_ENVIRONMENT=production` so the API refuses to start without it. Losing the master
  key loses the data. See DATA_SEGREGATION_PLAN.md §9.
- **Encrypt before the first real file.** Encrypting later leaves plain-text copies behind
  in earlier backups (e.g. Time Machine snapshots) and in deleted disk blocks. On a new
  server, set the master key before any real patient data is loaded.
- **HTTPS.** Use `deploy/Caddyfile.production` (automatic Let's Encrypt certificate, HSTS,
  content security policy), keep the API on 127.0.0.1, and set `RCM_COOKIE_SECURE=1` and
  `RCM_ALLOWED_ORIGINS` to the app's address (production mode refuses to start without the
  first). Tested locally with `deploy/https-local.sh`; see the README.
- **BAAs.** Record each organisation's signed BAA on the Platform page before loading its
  real data; in production mode an organisation without one can't sign in.
- **Key service.** Pick a cloud key service, add its provider (`key_providers.py`, about one
  small class; see DATA_SEGREGATION_PLAN.md §9.6), and move the key to it with `rotate-key`.
  Production logs a warning while the key is still in `.env`.
- **Single sign-on.** Add the identity provider the clients use (OpenID Connect covers
  Entra ID, Okta, and Google; DATA_SEGREGATION_PLAN.md §9.7) and its screens, link each
  person's SSO ID, mark a break-glass administrator, then make sign-in SSO only.
- **Audit-log retention.** Events are kept 6 years (HIPAA's documentation period); set
  `RCM_AUDIT_RETENTION_YEARS` higher if a state or contract requires it. Once a year, run
  `python -m app.orgs audit-purge --dry-run`, then with `--by "Your Name"`, if your policy is to
  delete what's past retention. Back up the `logs/` folders with the rest of the data.
- **Audit log copy outside the server.** The log catches removal by anyone without the
  encryption key, but not an older copy restored whole, or someone holding the key. Copy
  `logs/audit-head.json` or the log itself somewhere the server can't overwrite, such as
  write-once storage, and compare during reviews.
- **Compliance items still open**: a BAA/DPA with Anthropic and the clearinghouse.

## Planned feature updates: claim submission

ClaustraRCM sits alongside a hospital's billing system rather than replacing it. Each
organisation sets a default route, and either route can be used on any claim:

- **Validate only:** check and correct here, export, and send from the hospital's own
  billing system. Draft -> Handed off.
- **Send through ClaustraRCM:** Draft -> Pending, with its 837 saved. Sending for real needs
  the clearinghouse connection below.

Build order:

- [x] **Choosing the route.** Organisation default (Users page), both routes on each draft,
  the Handed off status, and duplicate protection: a claim takes one route, and reopening a
  handed-off claim requires confirming the billing system hasn't sent it.
- [x] **Corrected claim export.** After hand-off: the claim's 837 with its corrections (under
  the hospital's own claim number if it was uploaded with one) and a list of what changed,
  both audited. One claim at a time; a batch export for validate-only hospitals is still to come.
- [x] **Claim file settings.** Administrators keep the 837 identifiers on the Users page. Hand-off
  files need no clearinghouse, and a facility with a 5-digit ZIP on file can be given its ZIP+4.
- [x] **Standard API.** Hospital systems send a claim or an 837/CSV file with an API key and get
  back its errors and suggested fixes (`/api/v1`). The hospital's claim number identifies the claim,
  so sending it again replaces the Draft. Not yet tried with a real hospital system.
- [x] **Self-updating patient list.** A patient on a claim is matched and updated, or added, never
  refused for being new; an unclear match is flagged for staff, not merged. Still to do: merging
  confirmed duplicates, and how long a patient stays on the list after their last claim.
- [x] **Prior authorization lists.** Each payer's list of services needing prior authorization
  (Users page). A listed service with no authorization is flagged however the claim arrived. A payer
  without a list is shown as not assessed. Lists are entered by hand and depend on the hospital
  keeping them current.
- [x] **Saying what wasn't checked.** Claims report coverage as not checked, and prior authorization
  as not assessed where there's no list, on the claim's page and in the API.

After the pilot, shaped by what it teaches us:
- [ ] **Eligibility check (is coverage active?).** Needs a 270/271 route, likely through the
  clearinghouse. Questions for the pilot: how does the hospital check coverage today, and when?
  How many denials are for lapsed coverage? Would it use a check here, or does its own system
  already do it?
- [ ] **Payer outcomes.** Features 1 and 2 below, with 835 upload optional for validate-only
  hospitals so they can see whether denials fell.
- [ ] **Clearinghouse connection.** Feature 5 below, once a vendor is chosen and the BAA signed.

Features 3 and 4 can follow when real volume flows or a client asks.

1. **Record payer decisions.** Enter the payer's decision by hand (paid and adjusted
   amounts, CARC/RARC denial codes), or import an 835 remittance file to update claims
   in bulk. Claims become Paid or Denied; denials enter the Needs attention queue with
   appeal suggestions and feed the Overview and future risk scores. Model it on
   `Data/raw_data/fact_remittance.csv`.
2. **Correct and resubmit, or void.** Send a corrected replacement (837 claim frequency
   code 7) or void one sent in error (code 8), as a new 837 linked to the original
   claim and its payer claim number. Depends on 1 for the payer's response.
3. **Batch submission.** Submit selected claims together and produce one 837 per day
   (one interchange, many claims) for the clearinghouse.
4. **Second approval before submission.** One person prepares, another approves (maker /
   checker), recorded in the audit log. Independent of the others.
5. **Clearinghouse connection.** Send 837s automatically (SFTP or API) and read back the
   999 and 277CA acknowledgements (accepted / rejected). Needs a chosen vendor,
   credentials, and a business associate agreement first; complete
   `backend/edi_settings.json` and validate a test file with them before going live.

## Payer documents behind the rules

Administrators upload a payer's own documents (provider manual, prior authorization list,
policy bulletin), so rules and the assistant can point to the payer's actual words.

- [x] **Stage 1: documents as evidence.** Upload a PDF or text document per payer on the Rules
  page, with its effective date (each organisation's own, encrypted with its key, in its data
  export). A rule can cite a document, page and passage; flagged claims and AI Fix show that
  source, and the assistant searches the documents and cites them by page. A document a rule
  cites can't be deleted until the rule stops citing it. A document can also be uploaded from
  the rule form's Source section (the rule's payer preselected), and is cited at once.
- [ ] **Stage 2: draft rules suggested from a document.** Claude reads an uploaded document and
  proposes rules, each with the passage it came from; an administrator accepts, edits or rejects
  each one, and nothing goes live on its own. Proposals the rule builder can't express (time
  limits, frequency per patient) are listed as needing a new kind of check. A newer version of a
  document flags the rules based on the older one for review. Questions for the pilot: which
  payers' documents hospitals have, and in what form.

## Onboarding hospitals (Platform page)

Today a hospital asks for a pilot through the website form, which opens an email to the
founder; after talking to them, a platform account creates the organisation on the Platform
page and then, as a separate step, adds its first administrator.

- [x] **Organisation and first administrator in one step.** The New organisation form takes the
  first administrator (name, username, password) too. Everything about the administrator is
  checked first, and if creating them still fails the organisation is removed again, so no
  organisation is left without an administrator. Further administrators are added on its row.
  Their email address comes with the invitation below.
- [x] **Temporary password, changed at first sign-in.** A password someone else chose (a new
  organisation's first administrator, another administrator added on the Platform page, an
  account added on the Users page, or a reset by an administrator) is temporary. After signing
  in with it, the person sees only a "Choose your own password" screen: they enter the password
  they were given and a new one, and nothing else opens until they do (the API refuses every
  other request with 403). Changing it ends their other sessions; wrong current passwords count
  towards the sign-in lockout. Anyone can also change their own password from the account menu.
  Accounts made with `python -m app.users` are not affected.
- [ ] **Invitation instead of a password (later).** The first administrator gets an emailed
  link to set their own password (expires in 72 hours, single use), so the platform account
  never chooses or sees a hospital's password. Needs an email service (e.g. Resend or
  Postmark) and a domain of our own to send from, with a signed agreement. Until then the
  temporary password above is given in person or by phone.
- [x] **Pilot requests approval list.** The website's pilot form saves each request on the
  server, and still opens the visitor's email app with a copy addressed to the founder (so a
  request arrives even if saving fails, and the founder hears of each one without an email
  service). The Platform page lists requests as Pending, with **Approve** (the New organisation
  form filled in from the request: organisation name and ID, the contact as first
  administrator with a temporary password; creates both, then marks the request Approved) and
  **Decline** (with a reason, kept for the record). Nothing is emailed to the requester either
  way: the founder contacts them.
  - Spam protection: a hidden honeypot field (filled-in requests are answered but not kept),
    at most 3 requests per email address and 5 per network address a day, 30 an hour overall,
    and 200 waiting. No account is created until approved. The limits are kept in memory, so a
    restart resets them; add a challenge such as Cloudflare Turnstile if spam gets through.
  - The requests hold personal data (name, work email, job title), not patient data: a privacy
    notice on the form, kept in the platform's own encrypted store (`_platform/`, with its own
    data key, included in `rotate-key` and `key-status`), deleted 12 months after a decision,
    and every view, approval and decline in the platform audit log (by request ID; the
    details aren't copied into the log).
  - Approval doesn't mean the hospital can load real claims: its BAA must still be recorded
    before go-live, as now.
  - Later, with the email service: email the founder from the server instead of the visitor's
    email app, and send the approved administrator an invitation instead of a password.

## Client-facing documentation

- [x] **Architecture and product document for client discussions** (`CLIENT_OVERVIEW.md`). A plain-language explanation of how the tool is built (frontend, backend, data per organisation, security and compliance, the assistant and what it shares with Claude, the claim routes), with a diagram, written for hospital IT, compliance and revenue cycle leads. Build it from `PROJECT_GUIDE.md`, `README.md` and `DATA_SEGREGATION_PLAN.md`.

## Summary

| Phase | Status |
|-------|--------|
| 1. Environment & Skeleton | Complete |
| 2. Data Layer & Claims API | Complete |
| 3. Validation Engine | Complete |
| 4. Claims Workbench | Complete |
| 5. Rule Manager & Builder | Complete |
| 6. AI Fix Workflow | Complete |
| 7. Executive Dashboard | Complete |
| 8. JAB Audit | Complete |
| 9. Polish & Testing | Complete |
| 10. RAG Clarification Assistant | Complete |

*Created: 2026-10-16*
