# ClaustraRCM — Claim Validation Tool

Pre-submission claim validation and denial prevention for hospital revenue cycle teams.
Every claim is checked against configurable rules and scored for denial risk; flagged claims
get rule-based fix suggestions, and an executive dashboard tracks the results. Built with a
FastAPI backend and a React frontend over a synthetic 120,000-claim data set.

## What it does

| Page | Purpose |
|---|---|
| **Dashboard** | KPIs (denial rate, clean claim rate, days in AR, net collection, at-risk claims) against the prior period, revenue trend, validation status, top denial reasons, AR aging, payer performance. Filter by period, payer, department. |
| **Claims Workbench** | Search and filter all claims; each row shows its validation result and 0–100 risk score. Expand a claim for findings, risk breakdown, lines, denials, and **AI Fix** suggestions that can be applied and undone. Suggestions that need judgement (medical necessity, NCCI/modifiers, payer prior auth, appeals) offer **Ask the assistant**. |
| **New Claim** | Enter a draft claim for a registered patient: billed payer (defaults to the registered primary) plus secondary/tertiary coverage, up to 12 diagnoses each supported by a service line, prior authorization. It's validated on creation and can be marked submitted once rule errors are resolved. |
| **Rule Manager** | Create, edit, enable/disable, and test rules (field + operator + value conditions, AND/OR, scoped to payers, departments, or claim types). Changes apply to every claim immediately. |
| **JAB Audit** | Conceptual integration with the JAB Audit underpayment recovery platform: workflow, architecture, and the proposed API contracts. |

### Clarification assistant

Answers a billing specialist's questions from the organization's reference tables, citing
each record it relies on as [S1], [S2]:

| Use case | Sources |
|---|---|
| Medical necessity | LCD/NCD coverage policies (`ref_lcd_ncd_policies`) |
| NCCI / modifiers | NCCI PTP edits, MUE limits (`ref_ncci_ptp_edits`, `ref_mue_limits`) |
| Payer prior auth and terms | Payer profiles and contracts (`dim_payers`, `dim_payer_contracts`) |
| Appeal wording | CARC/RARC codes (`ref_carc_codes`, `ref_rarc_codes`), plus the above |
| Expected payment | Medicare fee schedule (`ref_physician_fee_schedule`) |

Retrieval is deterministic: the claim's CPT, ICD-10, payer, and CARC/RARC codes look up the
records that govern them (e.g. an NCCI edit when both of its codes are billed, an MUE when units
exceed the limit, a coverage policy noting whether the diagnosis is on its covered list), and
keyword search handles free-typed questions. Claude then writes the answer from those records
only. Without `ANTHROPIC_API_KEY` the assistant returns the matching records instead.

**Shared with Claude:** codes and amounts only (CPT, ICD-10, modifiers, units, payer, claim
type, place of service, charges, prior auth status, CARC/RARC, service year). Never patient
or provider names, IDs, age, gender, ZIP, NPI, PA numbers, any date finer than the year, or
denial free text. In the question, IDs, dates, and the names of registered patients and
providers are masked. The panel shows exactly what was shared.

### Sign-in, roles, and the audit log

Every route except `/api/health` needs a signed-in user, and each role gets only what it needs:

| Role | Can |
|---|---|
| `analyst` | View claims, validation, suggestions, dashboard, assistant. No patient names or demographics. |
| `biller` | Also see patient details and search patients, enter and submit claims, apply and undo fixes |
| `admin` | Also create and edit validation rules, and read the audit log |

Sessions are an HttpOnly, SameSite=Strict cookie. They end after 15 minutes without a request,
after 8 hours, at sign-out, or when the account is disabled; the API restarting also ends
them. Passwords are salted scrypt hashes, at least 12 characters with mixed case and a digit
or symbol, and five wrong attempts lock the account for 15 minutes.

Every API request is appended to `backend/logs/audit.jsonl` with the user, the action, the
records involved, search parameters, and the outcome (success, denied, failed). Each event
holds the hash of the one before it, so an edited or deleted line is detected; the Audit Log
page (admins) shows events and checks the chain. Questions to the assistant aren't logged,
only the claim they concern. Applied corrections also record who applied them.

### Claim lifecycle

```
Draft ──(Mark as submitted)──▶ Pending ──▶ Paid / Denied
                                  └─ Overdue: pending longer than the payer's average days to pay
```

Submission is blocked while a claim has rule errors. Drafts aren't counted in denial rate or AR.

### Risk score (0–100)

25 points per rule error, 10 per warning, 20 for prior patient denials (+5 if preventable),
5–15 for AR aging past 30/60/90 days, 15 for missing prior auth, 10 for a missing diagnosis.
Capped at 100. A non-clean claim counts once, through the Non-Clean Claim Review rule (a
warning), not again as a risk factor. New claims start clean. A claim with an error and a score of 60+ is routed to AI Fix.

## Setup

Prerequisites: Python 3.12+ with [uv](https://docs.astral.sh/uv/), Node.js 20.19+ or 22.12+, and the
synthetic data in `../Data/raw_data/`.

```bash
# Backend — from the repository root (Healthcare_RCM_Project/)
uv sync
cd claim_validation_tool/backend
uv run python -m app.users add yourname --name "Your Name" --role admin   # prompts for a password
uv run uvicorn app.main:app --reload --port 8000
```

Manage accounts with `uv run python -m app.users` (`list`, `add`, `password`, `role`,
`disable`, `enable`); changes apply while the API runs. Accounts live in `backend/users.json`
(git-ignored, readable only by you).

To have Claude answer the clarification assistant's questions, put the key in
`backend/.env` (git-ignored) as `ANTHROPIC_API_KEY=...` and start the API with
`uv run --env-file .env uvicorn app.main:app --reload --port 8000`.

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
| `ANTHROPIC_API_KEY` | unset | Enables Claude for the clarification assistant |
| `RCM_ASSISTANT_MODEL` | `claude-sonnet-5-5` | Claude model the assistant uses |
| `RCM_ASSISTANT_MODE` | | Set to `retrieval` to keep Claude off even with a key |
| `RCM_USERS_FILE` | `backend/users.json` | Sign-in accounts |
| `RCM_AUDIT_FILE` | `backend/logs/audit.jsonl` | Audit log |
| `RCM_SESSION_IDLE_MINUTES` | `15` | Sign out after this long without a request |
| `RCM_SESSION_MAX_HOURS` | `8` | Longest a session lasts |
| `RCM_COOKIE_SECURE` | off | Set to `1` behind HTTPS so the session cookie is never sent over plain HTTP |
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

Assistant evaluation, 17 billing questions with expected sources and answer facts
(`backend/app/evals/assistant_cases.py`):

```bash
cd claim_validation_tool/backend
uv run python -m app.evals.assistant          # retrieval recall and MRR (free, offline)
uv run --env-file .env python -m app.evals.assistant --llm   # also grades Claude's answers
```

Backend tests run against small fixture CSVs in `backend/app/tests/fixtures/`, never the real
data; `test_workflow.py` walks one claim from patient search to overdue. Frontend tests use
Vitest and Testing Library with `fetch` stubbed (`src/test/mockApi.js`).

## API

All routes are under `/api`; full schemas at `/docs`.

| Area | Endpoints |
|---|---|
| Sign-in | `POST /auth/login` · `POST /auth/logout` · `GET /auth/me` |
| Audit | `GET /audit` (username, record_id, outcome, limit) · `GET /audit/verify` |
| Claims | `GET /claims` (search, filter, sort, page) · `POST /claims` · `GET /claims/{id}` · `POST /claims/{id}/submit` |
| Validation | `GET /validate/{id}` · `POST /validate` (up to 200 claims) |
| Rules | `GET/POST /rules` · `GET/PUT/PATCH/DELETE /rules/{id}` · `GET /rules/fields` · `POST /rules/test` |
| AI Fix | `GET /aifix/{id}` · `POST /aifix/{id}/apply` · `DELETE /aifix/{id}/corrections` |
| Dashboard | `GET /dashboard` (months, payer_id, department_id) |
| Reference | `/patients`, `/patients/{id}`, `/payers`, `/departments`, `/providers`, `/facilities`, `/codes/procedures`, `/codes/diagnoses` |
| Assistant | `POST /assistant` (question, optional claim_id and topic) · `GET /assistant/status` |
| JAB Audit | `GET /jab/contracts` |
| Health | `GET /health` |

Errors return `{"detail": ...}`: a message for 401 (signed out), 403 (role lacks the
permission), 404/409/422 business errors, or FastAPI's field list for request validation errors.

## Project structure

```
claim_validation_tool/
├── PROJECT_GUIDE.md        # Architecture, conventions, domain context
├── PHASES.md               # Build phases and progress
├── backend/app/
│   ├── main.py             # FastAPI app, CORS, audit middleware, routers, data preload
│   ├── users.py            # Account management CLI (python -m app.users)
│   ├── routers/            # One module per API area
│   ├── models/             # Pydantic request/response schemas
│   ├── services/           # Validation engine, risk scorer, AI fix, assistant, dashboard, JAB
│   ├── data/               # Claims repository, rule/correction/user stores, audit log, knowledge base
│   ├── evals/              # Assistant evaluation set and runner
│   └── tests/              # pytest suite and fixture CSVs
└── frontend/src/
    ├── App.jsx             # Shell and hash routes
    ├── pages/              # Login, Dashboard, ClaimsWorkbench, NewClaim, RuleManager, JabAudit, AuditLog
    ├── components/         # Shared UI (badges, panels, builders, error boundary)
    ├── hooks/              # Data hooks built on useApi
    ├── services/api.js     # The only place that calls fetch
    ├── utils/              # Formatting, routes, rule summaries, claim entry helpers
    └── test/               # Vitest setup and fetch mock
```

## Limitations

- Synthetic data: payer, coding (LCD/NCCI/MUE), and contract checks are limited to what it contains.
- Not yet fit for real patient data: no HTTPS or encryption at rest, local accounts rather than
  single sign-on, and no agreement (BAA/DPA) with Anthropic. Sessions live in memory, so a
  restart signs everyone out, and the audit log has no rotation or retention policy.
- AI Fix is rule-based; the assistant handles the ambiguous cases. Its knowledge is limited to
  the reference tables: there are no payer policy manuals, so it can't say which services a
  payer requires prior authorization for, or quote filing limits, and says so.
