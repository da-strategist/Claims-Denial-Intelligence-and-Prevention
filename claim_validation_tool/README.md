# ClaustraRCM — Claim Validation Tool

Pre-submission claim validation and denial prevention for hospital revenue cycle teams.
Every claim is checked against configurable rules and scored for denial risk; flagged claims
get rule-based fix suggestions, and an executive dashboard tracks the results. Built with a
FastAPI backend and a React frontend over a synthetic 120,000-claim data set.

## What it does

| Page | Purpose |
|---|---|
| **Dashboard** | KPIs (denial rate, clean claim rate, days in AR, net collection, at-risk claims) against the prior period, revenue trend, validation status, top denial reasons, AR aging, payer performance. Filter by period, payer, department. |
| **Claims Workbench** | Search and filter all claims; each row shows its validation result and 0–100 risk score. Expand a claim for findings, risk breakdown, lines, denials, and **AI Fix** suggestions that can be applied and undone. |
| **New Claim** | Enter a draft claim for a registered patient: billed payer (defaults to the registered primary) plus secondary/tertiary coverage, up to 12 diagnoses each supported by a service line, prior authorization. It's validated on creation and can be marked submitted once rule errors are resolved. |
| **Rule Manager** | Create, edit, enable/disable, and test rules (field + operator + value conditions, AND/OR, scoped to payers, departments, or claim types). Changes apply to every claim immediately. |
| **JAB Audit** | Conceptual integration with the JAB Audit underpayment recovery platform: workflow, architecture, and the proposed API contracts. |

### Claim lifecycle

```
Draft ──(Mark as submitted)──▶ Pending ──▶ Paid / Denied
                                  └─ Overdue: pending longer than the payer's average days to pay
```

Submission is blocked while a claim has rule errors. Drafts aren't counted in denial rate or AR.

### Risk score (0–100)

25 points per rule error, 10 per warning, 20 for prior patient denials (+5 if preventable),
5–15 for AR aging past 30/60/90 days, 15 for missing prior auth, 10 for a missing diagnosis,
5 for a non-clean claim. Capped at 100. A claim with an error and a score of 60+ is routed to AI Fix.

## Setup

Prerequisites: Python 3.12+ with [uv](https://docs.astral.sh/uv/), Node.js 20.19+ or 22.12+, and the
synthetic data in `../Data/raw_data/`.

```bash
# Backend — from the repository root (Healthcare_RCM_Project/)
uv sync
cd claim_validation_tool/backend
uv run uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs. Loading the data takes a few seconds at startup.

```bash
# Frontend — in a second terminal
cd claim_validation_tool/frontend
npm install
npm run dev
```

App: http://localhost:5173. The Vite dev server proxies `/api` to port 8000.

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `RCM_DATA_DIR` | `Data/raw_data` at the repository root | Directory with the source CSVs |
| `RCM_RULES_FILE` | `backend/rules.json` | Saved rules (seeded with 9 defaults on first run) |
| `RCM_CORRECTIONS_FILE` | `backend/claim_corrections.json` | Applied AI Fix corrections |
| `VITE_API_BASE` | `/api` | API base URL for the frontend |

Rules and corrections persist in those JSON files (git-ignored). Claims entered on the New
Claim page are held in memory and are gone after a restart; their corrections are dropped then too.

## Testing

```bash
cd claim_validation_tool/backend && uv run python -m pytest   # API, engine, risk, AI fix, workflow
cd claim_validation_tool/frontend && npm test                 # components, pages, hooks, API client
npm run lint                                                  # oxlint
npm run build                                                 # production build
```

Backend tests run against small fixture CSVs in `backend/app/tests/fixtures/`, never the real
data; `test_workflow.py` walks one claim from patient search to overdue. Frontend tests use
Vitest and Testing Library with `fetch` stubbed (`src/test/mockApi.js`).

## API

All routes are under `/api`; full schemas at `/docs`.

| Area | Endpoints |
|---|---|
| Claims | `GET /claims` (search, filter, sort, page) · `POST /claims` · `GET /claims/{id}` · `POST /claims/{id}/submit` |
| Validation | `GET /validate/{id}` · `POST /validate` (up to 200 claims) |
| Rules | `GET/POST /rules` · `GET/PUT/PATCH/DELETE /rules/{id}` · `GET /rules/fields` · `POST /rules/test` |
| AI Fix | `GET /aifix/{id}` · `POST /aifix/{id}/apply` · `DELETE /aifix/{id}/corrections` |
| Dashboard | `GET /dashboard` (months, payer_id, department_id) |
| Reference | `/patients`, `/patients/{id}`, `/payers`, `/departments`, `/providers`, `/facilities`, `/codes/procedures`, `/codes/diagnoses` |
| JAB Audit | `GET /jab/contracts` |
| Health | `GET /health` |

Errors return `{"detail": ...}`: a message for 404/409/422 business errors, or FastAPI's
field list for request validation errors.

## Project structure

```
claim_validation_tool/
├── PROJECT_GUIDE.md        # Architecture, conventions, domain context
├── PHASES.md               # Build phases and progress
├── backend/app/
│   ├── main.py             # FastAPI app, CORS, routers, data preload
│   ├── routers/            # One module per API area
│   ├── models/             # Pydantic request/response schemas
│   ├── services/           # Validation engine, risk scorer, AI fix, dashboard, JAB
│   ├── data/               # In-memory claims repository, rule and correction stores
│   └── tests/              # pytest suite and fixture CSVs
└── frontend/src/
    ├── App.jsx             # Shell and hash routes
    ├── pages/              # Dashboard, ClaimsWorkbench, NewClaim, RuleManager, JabAudit
    ├── components/         # Shared UI (badges, panels, builders, error boundary)
    ├── hooks/              # Data hooks built on useApi
    ├── services/api.js     # The only place that calls fetch
    ├── utils/              # Formatting, routes, rule summaries, claim entry helpers
    └── test/               # Vitest setup and fetch mock
```

## Limitations

- Synthetic data: payer, coding (LCD/NCCI/MUE), and contract checks are limited to what it contains.
- No authentication or audit log; intended for local use.
- AI Fix is rule-based. A retrieval-augmented clarification assistant is planned (Phase 10).
