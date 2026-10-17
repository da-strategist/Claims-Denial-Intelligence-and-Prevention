# Project Guide — ClaustraRCM Claim Validation Tool

## Purpose

This tool validates healthcare claims against configurable rules, identifies denial risks, suggests AI-driven fixes, and provides executive-level dashboards — targeting C-suite decision-makers at hospitals and health systems.

## Architecture

### Backend (Python / FastAPI)

**Why FastAPI:** async-capable, auto-generates OpenAPI docs, Pydantic validation, strong typing. Pairs with the existing Python/dbt analytics stack.

**Module layout:**

- `app/main.py` — FastAPI app instance, CORS, routers, data preload at startup
- `app/routers/` — one file per API domain:
  - `claims.py` — search, detail, manual entry, and submission of claims
  - `rules.py` — CRUD and dry-run testing for validation rules
  - `validation.py` — run the validation engine against claims
  - `aifix.py` — fix suggestions, applying them, and undoing corrections
  - `assistant.py` — clarification questions answered with cited reference records
  - `dashboard.py` — aggregated KPIs and chart data
  - `patients.py`, `payers.py`, `departments.py`, `reference.py` — lookups for the UI
  - `jab.py` — JAB Audit integration contracts (conceptual)
- `app/models/` — Pydantic schemas for request/response contracts
- `app/services/` — business logic, decoupled from HTTP:
  - `validation_engine.py` — evaluates rules against claims (vectorized over pandas)
  - `risk_scorer.py` — composite risk score calculation
  - `aifix.py` — rule-based fix suggestions with citations
  - `assistant.py` — clarification assistant: claim facts, retrieval, Claude answer writer
  - `status_snapshot.py` — cached validation of every claim, invalidated on data or rule changes
  - `dashboard.py`, `jab.py` — dashboard aggregates and JAB contract schemas
- `app/data/` — data access: in-memory claims repository over the synthetic CSVs, JSON-backed
  rule and correction stores, reference data (CPT, ICD-10, contracts, CARC/RARC), and the
  assistant's knowledge base (`knowledge.py`: one citable source per reference-table row)
- `app/evals/` — the assistant's evaluation set and runner

**Conventions:**
- All API routes prefixed with `/api/`
- Pydantic models for all request/response bodies
- Services never import from routers (dependency flows inward)
- Type hints on all function signatures

### Frontend (React / Vite)

**Module layout:**

- `src/pages/` — one component per view:
  - `Dashboard.jsx` — KPI cards, charts
  - `ClaimsWorkbench.jsx` — searchable/filterable claim table with expandable rows
  - `NewClaim.jsx` — manual claim entry for registered patients
  - `RuleManager.jsx` — rule list + rule builder panel
  - `JabAudit.jsx` — conceptual audit workflow
- `src/components/` — reusable pieces (StatusBadge, KpiCard, ConditionBuilder, etc.)
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
- Missing prior auth: 15 pts
- Missing diagnosis: 10 pts
- Non-clean claim: scored only through rule findings (Non-Clean Claim Review), so it isn't counted twice

## Clarification Assistant: Data Handling

Rules handle the clear-cut cases; the assistant answers clarification questions where they
can't. It reads only the reference tables, and only `ClaimFacts` leaves the system:

| Sent to Claude | Never sent |
|---|---|
| CPT, category, modifier, units, line charge, ICD-10 pointer | Patient name, ID, age, gender, ZIP |
| Primary and additional ICD-10 | Claim ID, provider name, provider ID, NPI |
| Payer ID, name, type; other payer IDs | Exact service, submission, or denial dates |
| Claim type, place of service, status, service month | Prior auth number (only whether one exists) |
| Total charge and paid, days in AR, PA required/obtained | Denial reason free text |
| Denial CARC/RARC, root cause category, amount, preventable | |

Questions are scrubbed of patient/claim/provider IDs, 10-digit numbers, and dates before
retrieval or sending. Any new field added to `ClaimFacts` must stay within this list; the
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
