# Project Guide — ClaustraRCM Claim Validation Tool

## Purpose

This tool validates healthcare claims against configurable rules, identifies denial risks, suggests AI-driven fixes, and provides executive-level dashboards — targeting C-suite decision-makers at hospitals and health systems.

## Architecture

### Backend (Python / FastAPI)

**Why FastAPI:** async-capable, auto-generates OpenAPI docs, Pydantic validation, strong typing. Pairs with the existing Python/dbt analytics stack.

**Module layout:**

- `app/main.py` — FastAPI app instance, CORS, audit middleware, routers, data preload at startup
- `app/users.py` — account management CLI
- `app/routers/` — one file per API domain:
  - `claims.py` — search, detail, manual entry, submission (with its 837), and the 837 and PDF downloads
  - `drafts.py` — saved drafts of the New Claim form
  - `rules.py` — CRUD and dry-run testing for validation rules
  - `validation.py` — run the validation engine against claims
  - `aifix.py` — fix suggestions, applying them, and undoing corrections
  - `assistant.py` — clarification questions answered with cited reference records
  - `dashboard.py` — aggregated KPIs and chart data
  - `patients.py` — patient search and each patient's registration (billing details to fill a claim)
  - `payers.py`, `departments.py`, `reference.py` — lookups for the UI
  - `jab.py` — JAB Audit integration contracts (conceptual)
  - `auth.py`, `audit.py` — sign-in and out; reading and verifying the audit log
  - `users.py` — account management for administrators (the Users page), with self-lockout guards
- `app/models/` — Pydantic schemas for request/response contracts
- `app/services/` — business logic, decoupled from HTTP:
  - `validation_engine.py` — evaluates rules against claims (vectorized over pandas)
  - `risk_scorer.py` — composite risk score calculation
  - `aifix.py` — rule-based fix suggestions with citations
  - `assistant.py` — clarification assistant: claim facts, retrieval, Claude answer writer
  - `status_snapshot.py` — cached validation of every claim, invalidated on data or rule changes
  - `dashboard.py`, `jab.py` — dashboard aggregates and JAB contract schemas
  - `auth.py` — sessions, login throttling, and the `require(permission)` route dependency
  - `edi837.py`, `edi_settings.py`, `edi_reader.py`, `claim_pdf.py` — build the 837 at submission
    from the claim and the organisation settings, read a saved 837 back, and render its PDFs
- `app/data/` — data access: claims repository over the synthetic CSVs (claims entered in the app
  are saved in `new_claims.json` and replayed on startup), JSON-backed rule, correction, saved-draft
  (`drafts.py`) and patient registration (`registrations.py`) stores, reference data (CPT, ICD-10, contracts, CARC/RARC), and the
  assistant's knowledge base (`knowledge.py`: one citable source per reference-table row),
  user accounts (`users.py`), and the hash-chained audit log (`audit.py`)
- `app/evals/` — the assistant's evaluation set and runner

**Conventions:**
- All API routes prefixed with `/api/`
- Pydantic models for all request/response bodies
- Services never import from routers (dependency flows inward)
- Type hints on all function signatures
- Every router declares the permission it needs (`dependencies=[require(Permission.X)]`), and
  write routes add a stricter one; `test_every_api_route_requires_sign_in` fails if a route
  is left open. Roles and their permissions are in `models/auth.py`

### Frontend (React / Vite)

**Module layout:**

- `src/pages/` — one component per view:
  - `Dashboard.jsx` — KPI cards, charts
  - `ClaimsWorkbench.jsx` — claim table with expandable rows; opens on the Needs attention queue (`needs_attention=true`, sorted by `risk_score`)
  - `NewClaim.jsx` — claim entry for registered patients, with the 837 billing fields filled from
    their registration, Save draft, and the shared Drafts panel (saved forms and draft claims)
  - `RuleManager.jsx` — rule list + rule builder panel
  - `JabAudit.jsx` — conceptual audit workflow
  - `AuditLog.jsx` — the audit log (admins)
  - `Users.jsx` — add accounts, change roles, reset passwords, disable / enable (admins)
  - `UserGuide.jsx` — task-by-task help, filtered to the signed-in role
- `src/components/` — reusable pieces (StatusBadge, KpiCard, ConditionBuilder, etc.)
- `src/index.css` — the design system: colour tokens (one blue accent for actions; green for good, amber for review, red for problems: Paid, Pass and low risk are green; warnings and medium risk amber; errors, denials and high risk red), and the shared `btn-primary`, `btn-secondary`, `btn-quiet`, `btn-danger`, `card`, `field` and `eyebrow` classes. New UI should use these rather than one-off colours.
- `src/components/PageHeader.jsx` — `Page` (width and padding), `PageHeader` (title, one line of context, actions) and `Notice` (inline error/warning); every page uses them
- `src/services/api.js` — centralized fetch wrapper for all backend calls
- `src/hooks/` — custom hooks for data fetching and state

**Conventions:**
- Functional components with hooks; the one exception is `ErrorBoundary`, which React only
  supports as a class
- Tailwind CSS v4 via the Vite plugin
- All API calls go through `services/api.js` — components never call fetch directly
- Props destructured in function signature
- Tests sit next to the code they cover (`*.test.js[x]`), run with Vitest and Testing Library

## Domain Context

### Key Healthcare RCM Concepts

- **Claim:** A request for payment submitted to a payer (insurance company) for healthcare services
- **Denial:** When a payer rejects a claim — costs hospitals an average of $25-$50 per reworked claim
- **CARC/RARC codes:** Claim Adjustment Reason Codes and Remittance Advice Remark Codes — standardized codes explaining why a claim was adjusted or denied
- **ICD-10:** International Classification of Diseases, 10th revision — diagnosis codes
- **CPT:** Current Procedural Terminology — procedure codes
- **Prior Authorization (PA):** Payer approval required before certain services are performed
- **Clean Claim Rate (CCR):** Percentage of claims accepted on first submission without edits
- **Days in AR:** Days a claim sits in Accounts Receivable before payment
- **Denial Rate:** Percentage of claims denied by payers

### Synthetic Data

The project uses synthetic data representing a 312-bed community hospital:
- 120K claims over 24 months
- ~22.3K denials (18% denial rate)
- ~76% clean claim rate
- $911M total billed
- 12 payers, including Medicare, Medicaid plans, UnitedHealthcare, Aetna, Blue Cross NC, Humana, Cigna, and Self-Pay
- Source CSVs in `../Data/raw_data/` (25 files, ~178MB total)

### Validation Rules

Rules evaluate claim fields against conditions:
- **Operators:** isEmpty, isNotEmpty, equals, notEquals, greaterThan, lessThan, contains
- **Scope:** all claims, or filtered by payer / claim type / department
- **Severity:** error (blocks claim), warning (flags for review), info
- **Categories:** Coding, Eligibility, Authorization, Demographics, Billing, Required Fields, Payer-Specific

### Risk Scoring (0-100)

Factors:
- Error count: 25 pts per error
- Warning count: 10 pts per warning
- Denial history: 20-25 pts
- AR aging over 30 / 60 / 90 days: 5 / 10 / 15 pts
- Missing prior auth: 15 pts, unless a rule testing prior auth (Missing Prior Authorization) already flagged the claim
- Missing diagnosis: 10 pts, unless a rule testing the primary diagnosis already flagged it
- Non-clean claim: scored only through rule findings (Non-Clean Claim Review)

A fact is never counted twice: an attribute factor only adds points when no enabled rule covers it.

### Submission

**Saved drafts are not claims.** The New Claim page's **Save draft** stores the form as it was left (`/api/drafts`), with nothing required beyond field formats. Saved drafts aren't validated, scored, listed in Claims, or counted on the Overview. They are shared by everyone who can enter claims, recorded in the audit log, kept in an owner-only file, and deleted 30 days after the last save (data minimisation). Creating the claim from a saved draft removes the draft.

**837 claim files.** `services/edi837.py` builds the 837P/837I from the claim, its `billing` details (`models/billing.py`), the payers, provider, and facility, and the organisation settings (`services/edi_settings.py`). It runs at submission; the text is saved in `new_claims.json` with the claim. Missing organisation settings (or a facility ZIP without +4) mark the file as a test file rather than inventing values. `services/edi_reader.py` reads a saved 837 back into named fields, and `services/claim_pdf.py` (reportlab) renders the CMS-1500/UB-04 and readable-837 PDFs from it. Patients' billing details come from `data/registrations.py`: entered details first, else deterministic sample details for the synthetic patients.

**Draft claims are finished on New Claim, not in Claims.** The workbench asks for `include_drafts=false`; the New Claim page's Drafts panel lists both saved forms and draft claims (`GET /claims?status=Draft`), and opens a draft claim with its findings, fixes, and submission in place. The page is open to every role that can enter claims, so any biller can pick up anyone's draft.

Every new claim starts as a Draft, whether it's entered on the New Claim page or sent to `POST /claims` directly (a `status` in the request is ignored). `POST /claims/{id}/submit` is the only way a claim leaves Draft. It runs the enabled rules again at that moment, judging the claim as if it goes out today (not on its planned date), and refuses it while any **error or warning** remains, naming the rules. A draft whose planned date has passed is already shown as of today, so rules like Timely Filing Risk flag it before anyone tries to submit. Info findings don't block. To submit, fix the claim (e.g. with AI Fix) or, as an administrator, disable or change the rule.

## Clarification Assistant: Data Handling

Rules handle the clear-cut cases; the assistant answers clarification questions where they
can't. It reads only the reference tables, and only `ClaimFacts` leaves the system:

| Sent to Claude | Never sent |
|---|---|
| CPT, category, modifier, units, line charge, ICD-10 pointer | Patient name, ID, age, gender, ZIP |
| Primary and additional ICD-10 | Claim ID, provider name, provider ID, NPI |
| Payer ID, name, type; other payer IDs | Any date element finer than the year (HIPAA Safe Harbor) |
| Claim type, place of service, status, service year | Prior auth number (only whether one exists) |
| Total charge and paid, days in AR, PA required/obtained | Denial reason free text |
| Denial CARC/RARC, root cause category, amount, preventable | |

Questions are scrubbed of patient/claim/provider IDs, 10-digit numbers, dates, and people's
names before retrieval or sending. Names are matched against the registered patients and
providers ("Karen Sanchez", "Sanchez, Karen", "patient Sanchez", "Mrs. Sanchez"), plus any
capitalised word after a title; a lone first name or surname is left alone because so many
are ordinary words. Any new field added to `ClaimFacts` must stay within this list; the
test `test_claim_facts_share_codes_and_amounts_only` checks a real claim's identifiers never
reach the prompt.

## Data Flow

```
Raw CSVs (Data/raw_data/)
    ↓
dbt pipeline (rcm/) → BigQuery
    ↓
FastAPI data layer (app/data/) → loads the synthetic CSVs into memory (BigQuery later)
    ↓
Validation Engine (app/services/) → evaluates rules, scores risk
    ↓
API endpoints (app/routers/) → JSON responses
    ↓
React frontend (frontend/src/) → renders UI
```

## Related Project Files

- `../Claims_denial_skill/PROJECT_INSTRUCTIONS.md` — full platform vision and spec
- `../Data/raw_data/` — 25 source CSV files
- `../rcm/` — dbt project (staging + intermediate models)
- `../TASKS.md` — overall project task tracker
