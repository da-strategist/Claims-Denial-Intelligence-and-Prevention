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
