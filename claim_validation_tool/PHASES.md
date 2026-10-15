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
- [ ] Build AI fix suggestion service (backend)
- [ ] Create `/api/aifix` endpoint
- [ ] Add AI Fix actions to Claims Workbench expanded rows
- [ ] Apply fix and re-validate flow

## Phase 7: Executive Dashboard
- [ ] Create `/api/dashboard` endpoints (KPIs, chart data)
- [ ] Build KPI cards component
- [ ] Build charts (Revenue Trends, Denial Reasons, AR Aging, Claim Status)
- [ ] Connect to dashboard API

## Phase 8: JAB Audit Integration (Conceptual)
- [ ] Build workflow diagram component
- [ ] Build integration architecture cards
- [ ] Design future API contracts

## Phase 9: Polish & Testing
- [ ] Backend unit tests (validation engine, risk scorer, AI fix)
- [ ] Frontend component testing
- [ ] API integration tests
- [ ] UI polish and responsive design
- [ ] Error handling and loading states
- [ ] Final documentation

---

## Summary

| Phase | Status |
|-------|--------|
| 1. Environment & Skeleton | Complete |
| 2. Data Layer & Claims API | Complete |
| 3. Validation Engine | Complete |
| 4. Claims Workbench | Complete |
| 5. Rule Manager & Builder | Complete |
| 6. AI Fix Workflow | Pending |
| 7. Executive Dashboard | Pending |
| 8. JAB Audit | Pending |
| 9. Polish & Testing | Pending |

*Created: 2026-10-16*
