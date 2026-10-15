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
- [ ] Create Rule Pydantic model (conditions, scope, severity, category)
- [ ] Build validation engine service (evaluate conditions against claims)
- [ ] Build risk scoring service
- [ ] Create `/api/rules` endpoints (CRUD)
- [ ] Create `/api/validate` endpoint (run rules against claims)
- [ ] Create default rule set (seed data)

## Phase 4: Claims Workbench (Frontend)
- [ ] Build Claims table component with search, filter, sort
- [ ] Build expandable row with validation details
- [ ] Build status badges (Pass, Warning, Error, AI Fix)
- [ ] Connect to validation API
- [ ] Add pagination

## Phase 5: Rule Manager & Custom Rule Builder (Frontend)
- [ ] Build rule list view with toggle/edit/delete
- [ ] Build Rule Builder slide-in panel
- [ ] Build Condition Builder (field/operator/value, AND/OR logic)
- [ ] Build Test Rule functionality
- [ ] Connect to rules API

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
| 3. Validation Engine | Pending |
| 4. Claims Workbench | Pending |
| 5. Rule Manager & Builder | Pending |
| 6. AI Fix Workflow | Pending |
| 7. Executive Dashboard | Pending |
| 8. JAB Audit | Pending |
| 9. Polish & Testing | Pending |

*Created: 2026-10-16*
