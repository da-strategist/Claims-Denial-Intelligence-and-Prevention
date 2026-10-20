# ClaustraRCM — AI-Powered Claim Validation Prototype

A React-based prototype demonstrating AI-driven claim validation, denial prevention, and revenue cycle intelligence for hospital C-suite stakeholders.

## Quick Start

```bash
cd prototype
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

## Production Build

```bash
npm run build
```

The build output is in `build/` (already pre-built). To serve it:

```bash
npx serve build
```

## Features

### Executive Dashboard
- KPI cards: Total Claims, Denial Rate, Clean Claim Rate, Avg Days in AR
- Revenue Trends (line chart), Claim Status (donut), AR Aging (pie)
- Top Denial Reasons (bar chart), Monthly Collections (line chart)

### Claims Workbench
- Search by claim ID, patient, provider, or diagnosis
- Filter by status (Pass / Warning / Error / AI Fix) and payer
- Sortable columns (claim ID, patient, billed amount, risk score, status)
- Expandable rows showing validation failures, risk breakdown, and AI fix actions
- Pagination (15 claims per page)

### Rule Manager & Custom Rule Builder (Priority Feature)
- View, toggle, edit, and delete validation rules
- Slide-in Rule Builder panel with:
  - Rule Definition: name, description, severity, category
  - Scope Definition: apply to all claims or filter by payer/claim type/department
  - **Condition Builder**: add multiple conditions with field/operator/value selectors, AND/OR logic
  - **Test Rule**: run the rule against all claims and see pass/fail counts before saving
- 8 default rules covering missing diagnosis, missing PA, high billed amounts, AR aging, payer-specific coding

### AI Fix Workflow
- Deterministic fix suggestions for common denial root causes
- One-click "Apply Fix" on individual validation failures
- Fixes cover: missing diagnosis codes, missing prior auth, unspecified ICD-10 upgrades, high-value claim review

### JAB Audit Integration (Conceptual)
- 4-step workflow diagram: Payer Contract Ingestion → Remittance Matching → Variance Detection → Recovery Action
- Integration architecture cards showing future API/webhook design

## Architecture

```
prototype/
├── index.html              # Entry point (Tailwind CDN, Inter font, custom CSS)
├── vite.config.js           # Vite + React config
├── package.json
├── src/
│   ├── main.jsx             # React 18 entry
│   ├── App.jsx              # All views (Dashboard, Claims, Rules, JAB Audit)
│   ├── engine/
│   │   ├── validationEngine.js   # Rule evaluation engine
│   │   └── aiFix.js              # AI fix suggestion engine
│   └── data/
│       ├── syntheticClaims.js     # 60 enriched claim objects
│       ├── referenceData.js       # Payers, CARC/RARC, ICD-10, CPT codes
│       └── defaultRules.js        # 8 seed validation rules
└── build/                   # Pre-built production output
```

## Tech Stack

- React 18 + Vite
- Tailwind CSS (CDN)
- Recharts (charts)
- Lucide React (icons)

## Synthetic Data

60 claims representing a 312-bed community hospital, enriched with:
- Patient demographics, provider info, department assignment
- Payer details (6 payers including Medicare, Medicaid, UHC, Aetna, BCBS, Humana)
- Denial history with CARC/RARC codes
- Prior authorization status, AR aging, clean claim flags

## Validation Engine

Supports operators: `isEmpty`, `isNotEmpty`, `equals`, `notEquals`, `greaterThan`, `lessThan`, `contains`

Risk scoring (0-100) factors:
- Error count: 25 pts per error
- Warning count: 10 pts per warning
- Denial history: 20-25 pts
- AR aging > 60 days: 5-15 pts
- Missing prior auth: 15 pts
- Missing diagnosis: 10 pts
- Non-clean claim: 5 pts
