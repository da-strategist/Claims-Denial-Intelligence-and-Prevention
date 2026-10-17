# ClaustraRCM — Claim Validation Tool

Pre-submission claim validation and denial prevention for hospital revenue cycle teams.
Every claim is checked against configurable rules and scored for denial risk; flagged claims
get rule-based fix suggestions, and an executive dashboard tracks the results. Built with a
FastAPI backend and a React frontend over a synthetic 120,000-claim data set.

## What it does

| Page | Purpose |
|---|---|
| **Overview** | Opens on the number of submitted claims that need attention (the same claims the Claims queue shows), with a button straight to them, and for billers a line for draft claims still to finish on New Claim. Then KPIs (denial rate, clean claim rate, days in AR, net collection, at-risk claims) against the prior period, revenue trend, validation status, top denial reasons, AR aging, payer performance. Filter by period, payer, department. |
| **Claims** | Opens on the **Needs attention** queue: claims with validation errors (Error or AI Fix), riskiest first. **All claims** shows every submitted claim (drafts are finished on New Claim). Search and filter; each row shows its validation result and 0–100 risk score. Expand a claim for findings, risk breakdown, lines, denials, and **AI Fix** suggestions that can be applied and undone. Suggestions that need judgement (medical necessity, NCCI/modifiers, payer prior auth, appeals) offer **Ask the assistant**. A submitted claim shows its 837 with downloads (the file, a CMS-1500/UB-04 PDF, a readable PDF). Colours carry meaning: green for Paid, Pass and low risk; amber for warnings and medium risk; red for errors, denials and high risk. |
| **New Claim** | Enter a draft claim for a registered patient: selecting them fills in their primary payer, date of birth, address and member ID from their registration; billed payer plus secondary/tertiary coverage, each with its policy, up to 12 diagnoses each supported by a service line, prior authorization. A **Drafts** panel on the right lists everything waiting to be finished, shared by every biller: **saved forms** (from **Save draft**: unfinished, not validated, deleted 30 days after the last save) and **draft claims** (created and validated, not yet submitted). Opening a draft claim shows its problems, AI fixes, and **Mark as submitted**, which is only allowed once no rule error or warning remains. The same check applies to claims sent through the API. |
| **Rules** | Create, edit, enable/disable, and test rules (field + operator + value conditions, AND/OR, scoped to payers, departments, or claim types). Changes apply to every claim immediately. |
| **JAB Audit** | Conceptual integration with the JAB Audit underpayment recovery platform: workflow, architecture, and the proposed API contracts. |
| **User Guide** | Short task-by-task help for billers, analysts, and administrators. Each person sees only the sections their role can use. |

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
| `admin` | Also create and edit validation rules, manage user accounts, and read the audit log |

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

Submission is blocked while a claim has any rule error or warning, whether it was entered on screen or through the API. Draft claims are finished on the New Claim page, not listed under Claims, and aren't counted in denial rate or AR.

### 837 claim files

Every claim carries what an X12 837 needs, from the New Claim form or the API's `billing`
object: the patient's date of birth and address, each payer's policy (member ID, group,
and the policy holder when it isn't the patient), and for institutional claims the type of
bill, admission type and source, patient status, and a revenue code per line. Selecting a
patient fills these from their registration: what their last claim captured, or, for the
synthetic sample patients, generated sample details (marked as such). Creating a claim
saves its details back to the patient's registration.

**Mark as submitted** creates the 837P (professional) or 837I (institutional) and saves it
with the claim as the record of what was sent; billers and admins can download it, and each
download is audited. Self-pay claims are billed to the patient, so they get no 837.

Two PDFs are built from that saved file, so they always match what was sent: the claim on a
**CMS-1500** (837P) or **UB-04** (837I) layout with the official box numbers (a reference
copy for reading and printing, not the red-ink OCR form payers scan), and a **readable 837**
that names each part of the file, shows where every value sits, and ends with the raw file.
Test files carry a "TEST FILE" mark on every page.

The organisation's identifiers live in `backend/edi_settings.json` (git-ignored): submitter,
clearinghouse (receiver), billing provider (name, NPI, 9-digit EIN, address with ZIP+4), and
each payer's electronic payer ID. Until every one is set, `mode` is `production`, and the
facility address has a ZIP+4, files are marked as test files (ISA15 = T) and the claim lists
what's missing. See `app/services/edi_settings.py` for the file's shape.

### Risk score (0–100)

25 points per rule error, 10 per warning, 20 for prior patient denials (+5 if preventable),
5–15 for AR aging past 30/60/90 days, 15 for missing prior auth, 10 for a missing diagnosis.
Capped at 100. A fact is only counted once: missing prior auth or a missing diagnosis adds no extra
points when a rule already flags it. A non-clean claim counts once, through the Non-Clean Claim Review rule (a
warning), not again as a risk factor. New claims start clean. A claim with an error and a score of 60+ is routed to AI Fix.

## Setup

Prerequisites: Python 3.12+ with [uv](https://docs.astral.sh/uv/), Node.js 20.19+ or 22.12+, and the
synthetic data in `../Data/raw_data/`.

```bash
# Backend — from the repository root (Healthcare_RCM_Project/)
uv sync
cd claim_validation_tool/backend
uv run python -m app.orgs migrate        # creates the first organisation, "meridian", over Data/raw_data
uv run python -m app.orgs add-sample     # optional: the synthetic "lakeside" practice, for demos
uv run python -m app.users add yourname --name "Your Name" --role admin --org meridian   # prompts for a password
uv run uvicorn app.main:app --reload --port 8000
```

### Organisations

Several organisations can use one installation, each completely walled off from the others
(see `DATA_SEGREGATION_PLAN.md`). Each has its own folder under `backend/orgs/` (git-ignored,
readable only by the account running the API) holding its rules, corrections, saved drafts,
new claims and their 837s, patient registrations, 837 settings, and audit log, plus its own
claims CSVs. Every account belongs to one organisation, and every request reaches only that
organisation's data: another organisation's records are "not found". The sidebar shows the
organisation's name. `uv run python -m app.orgs list` shows organisations; `add` registers a
new one over its CSVs. `migrate` moves a single-organisation install into "meridian" and is
safe to run twice. An automated test tries every API route with another organisation's IDs.

### Accounts

The first administrator is created on the command line, as above. After that, administrators
manage accounts on the **Users** page (Admin section): add people, change roles, reset
passwords, and disable or re-enable accounts. Disabling or resetting a password signs that
person out; administrators can't change their own role or disable themselves, and the last
active administrator can't be demoted or disabled. Every change is audited (never the
password). Administrators only see and manage their own organisation's accounts; usernames
are unique across all organisations. The same is possible with `uv run python -m app.users`
(`list`, `add … --org`, `password`, `role`, `disable`, `enable`); changes apply while the API
runs. Accounts live in `backend/users.json` (git-ignored, readable only by you).

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
| `RCM_ORGS_DIR` | `backend/orgs` | Organisations: `organisations.json` and one folder per organisation with its `rules.json` (seeded with 9 defaults), `claim_corrections.json`, `claim_drafts.json` (expire 30 days after the last save), `new_claims.json` (with their 837s), `patient_registrations.json`, `edi_settings.json`, and `logs/audit.jsonl` |
| `ANTHROPIC_API_KEY` | unset | Enables Claude for the clarification assistant |
| `RCM_ASSISTANT_MODEL` | `claude-sonnet-5-5` | Claude model the assistant uses |
| `RCM_ASSISTANT_MODE` | | Set to `retrieval` to keep Claude off even with a key |
| `RCM_USERS_FILE` | `backend/users.json` | Sign-in accounts |
| `RCM_AUDIT_FILE` | `backend/logs/audit.jsonl` | Platform audit log: requests that belong to no organisation (e.g. sign-in with an unknown username). Each organisation's own log is in its folder |
| `RCM_SESSION_IDLE_MINUTES` | `15` | Sign out after this long without a request |
| `RCM_SESSION_MAX_HOURS` | `8` | Longest a session lasts |
| `RCM_COOKIE_SECURE` | off | Set to `1` behind HTTPS so the session cookie is never sent over plain HTTP |
| `VITE_API_BASE` | `/api` | API base URL for the frontend |

Each organisation's app data persists in its folder (git-ignored, readable only by the account
running the API). The source CSVs are never modified: new claims and their submission dates are
replayed on startup.

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
| Users | `GET /users` · `POST /users` · `PATCH /users/{username}` · `POST /users/{username}/password` (administrators) |
| Claims | `GET /claims` (search, filter, sort, page) · `POST /claims` · `GET /claims/{id}` · `POST /claims/{id}/submit` · `GET /claims/{id}/837` · `GET /claims/{id}/claim-form.pdf` · `GET /claims/{id}/837-readable.pdf` |
| Saved drafts | `GET /drafts` · `POST /drafts` · `GET /drafts/{id}` · `PUT /drafts/{id}` · `DELETE /drafts/{id}` (billers and admins) |
| Validation | `GET /validate/{id}` · `POST /validate` (up to 200 claims) |
| Rules | `GET/POST /rules` · `GET/PUT/PATCH/DELETE /rules/{id}` · `GET /rules/fields` · `POST /rules/test` |
| AI Fix | `GET /aifix/{id}` · `POST /aifix/{id}/apply` · `DELETE /aifix/{id}/corrections` |
| Dashboard | `GET /dashboard` (months, payer_id, department_id) |
| Reference | `/patients`, `/patients/{id}`, `/patients/{id}/registration`, `/payers`, `/departments`, `/providers`, `/facilities`, `/codes/procedures`, `/codes/diagnoses` |
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
│   ├── orgs.py             # Organisations CLI: list, add, migrate, add-sample
│   ├── sample_org.py       # Generates the synthetic Lakeside Family Practice
│   ├── routers/            # One module per API area
│   ├── models/             # Pydantic request/response schemas
│   ├── services/           # Validation engine, risk scorer, AI fix, assistant, dashboard, JAB,
│   │                       #   837 builder/reader/settings, claim PDFs
│   ├── data/               # Claims repository, rule/correction/user/draft/new-claim/registration
│   │                       #   stores, audit log, knowledge base
│   ├── evals/              # Assistant evaluation set and runner
│   └── tests/              # pytest suite and fixture CSVs
└── frontend/src/
    ├── App.jsx             # Shell and hash routes
    ├── pages/              # Login, Dashboard, ClaimsWorkbench, NewClaim, RuleManager, JabAudit, AuditLog, Users, UserGuide
    ├── components/         # Shared UI (badges, panels, builders, error boundary)
    ├── hooks/              # Data hooks built on useApi
    ├── services/api.js     # The only place that calls fetch
    ├── utils/              # Formatting, routes, rule summaries, claim entry helpers
    └── test/               # Vitest setup and fetch mock
```

## Limitations

- Synthetic data: payer, coding (LCD/NCCI/MUE), and contract checks are limited to what it contains.
  Some defaults suit only this sample (the Overview opens on All time, sample patient details are
  generated); `PHASES.md` lists what to change before going live on real claims.
- Not yet fit for real patient data: no HTTPS or encryption at rest, local accounts rather than
  single sign-on, and no agreement (BAA/DPA) with Anthropic. Sessions live in memory, so a
  restart signs everyone out, and the audit log has no rotation or retention policy.
- AI Fix is rule-based; the assistant handles the ambiguous cases. Its knowledge is limited to
  the reference tables: there are no payer policy manuals, so it can't say which services a
  payer requires prior authorization for, or quote filing limits, and says so.
