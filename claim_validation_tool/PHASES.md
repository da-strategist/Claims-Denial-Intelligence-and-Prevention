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
- **Encryption at rest.** Generate a master key (`uv run python -m app.orgs new-master-key`),
  put it in the key service (in `backend/.env` until then) with a backup copy kept
  separately, run `uv run python -m app.orgs encrypt` with the API stopped, and set
  `RCM_ENVIRONMENT=production` so the API refuses to start without it. Losing the master
  key loses the data. See DATA_SEGREGATION_PLAN.md §9.
- **BAAs.** Record each organisation's signed BAA on the Platform page before loading its
  real data; in production mode an organisation without one can't sign in.
- **Compliance items still open**: HTTPS (`RCM_COOKIE_SECURE=1`), moving the master key to
  a cloud key service, single sign-on, a BAA/DPA with Anthropic and the clearinghouse, and
  audit-log retention.

## Planned feature updates: claim submission

Not scheduled; to be built when the need arises. Today a claim goes Draft -> Pending
with its 837 saved and downloadable, and stays Pending (turning Overdue) because nothing
comes back from the payer. Suggested order: 1 then 2 complete the cycle without any
outside partner; 3 and 5 matter once real volume flows; 4 can be added at any time.

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
