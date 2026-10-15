# Project Guide — ClaustraRCM Claim Validation Tool

## Purpose

This tool validates healthcare claims against configurable rules, identifies denial risks, suggests AI-driven fixes, and provides executive-level dashboards — targeting C-suite decision-makers at hospitals and health systems.

## Architecture

### Backend (Python / FastAPI)

**Why FastAPI:** async-capable, auto-generates OpenAPI docs, Pydantic validation, strong typing. Pairs with the existing Python/dbt analytics stack.

**Module layout:**

- `app/main.py` — FastAPI app instance, middleware, startup events
- `app/routers/` — one file per API domain:
  - `claims.py` — CRUD and search for claims
  - `rules.py` — CRUD for validation rules
  - `validation.py` — run validation engine against claims
  - `dashboard.py` — aggregated KPIs and chart data
- `app/models/` — Pydantic schemas for request/response contracts
- `app/services/` — business logic, decoupled from HTTP:
  - `validation_engine.py` — evaluates rules against claims, computes risk scores
  - `ai_fix.py` — generates fix suggestions for flagged claims
  - `risk_scorer.py` — composite risk score calculation
- `app/data/` — data access layer (starts with synthetic data, later connects to BigQuery)

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
  - `RuleManager.jsx` — rule list + rule builder panel
  - `JABAudit.jsx` — conceptual audit workflow
- `src/components/` — reusable pieces (StatusBadge, KpiCard, ConditionBuilder, etc.)
- `src/services/api.js` — centralized fetch wrapper for all backend calls
- `src/hooks/` — custom hooks for data fetching and state

**Conventions:**
- Functional components with hooks (no class components)
- Tailwind CSS for styling (CDN for now, build step later if needed)
- All API calls go through `services/api.js` — components never call fetch directly
- Props destructured in function signature

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
- 6 payers: Medicare, Medicaid, UHC, Aetna, BCBS, Humana
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
- AR aging > 60 days: 5-15 pts
- Missing prior auth: 15 pts
- Missing diagnosis: 10 pts
- Non-clean claim: 5 pts

## Data Flow

```
Raw CSVs (Data/raw_data/)
    ↓
dbt pipeline (rcm/) → BigQuery
    ↓
FastAPI data layer (app/data/) → reads from BigQuery or synthetic data
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
