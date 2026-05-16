# Claims Denial Intelligence & Prevention Platform

A healthcare analytics engineering project that identifies revenue leakage, flags claims errors before submission, and reduces denials for hospitals and health systems.

Built with **dbt + BigQuery + Python**, designed to surface actionable insights for C-suite decision-makers across the revenue cycle.

---

## Project overview

This platform models claims, denials, remittance, workflow events, and payer data into analytics-ready mart tables that power executive dashboards. Key outputs include denial root cause analysis, payer scorecards, AR aging, clean claim rates, and revenue leakage quantification.

**Stack**: dbt-core · BigQuery · Python 3.12 · Tableau (visualization)

**Data**: 25 seed tables (120K claims, 22K denials, 8 dimension tables, 7 reference tables) representing a realistic multi-payer hospital environment.

---

## Getting started

### Prerequisites

Before cloning, make sure you have the following installed on your machine:

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.12+ | Runtime for dbt and scripts |
| [uv](https://docs.astral.sh/uv/) | latest | Fast Python package manager |
| Git | 2.x+ | Version control |
| Git LFS | latest | Large file support (seed CSVs are tracked via LFS) |
| Google Cloud SDK | latest | BigQuery authentication |

### 1. Clone the repository

```bash
git clone https://github.com/da-strategist/Claims-Denial-Intelligence-and-Prevention.git
cd Claims-Denial-Intelligence-and-Prevention
```

After cloning, pull the LFS-tracked data files:

```bash
git lfs install
git lfs pull
```

This downloads the 25 seed CSV files (~178 MB) into `Data/raw_data/`.

### 2. Set up the Python environment

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv --python 3.12
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# Install project dependencies
uv sync
```

### 3. Install dbt packages

```bash
cd rcm
dbt deps
```

This installs `dbt_utils` and any other packages listed in `packages.yml`.

### 4. Configure BigQuery access

#### a) Authenticate with Google Cloud

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project <YOUR_GCP_PROJECT_ID>
```

#### b) Create your profiles.yml

dbt looks for `profiles.yml` at `~/.dbt/profiles.yml`. Create this file with the following structure:

```yaml
healthcarercm:
  target: dev
  outputs:
    dev:
      type: bigquery
      method: oauth
      project: <YOUR_GCP_PROJECT_ID>
      dataset: dbt_<your_first_name>    # e.g. dbt_jubril, dbt_sarah
      threads: 4
      location: US                       # match your BigQuery dataset location
      timeout_seconds: 300
```

**Important notes:**

- The profile name `healthcarercm` must match exactly — it's referenced in `rcm/dbt_project.yml`.
- Each team member uses their own dataset (e.g. `dbt_jubril`, `dbt_aisha`) so work doesn't collide.
- The `oauth` method uses your `gcloud auth application-default` credentials. For CI/CD or service accounts, use `method: service-account` with a keyfile instead.

#### c) Verify the connection

```bash
cd rcm
dbt debug
```

You should see "All checks passed!" — this confirms dbt can reach BigQuery.

### 5. Load seed data

```bash
dbt seed
```

This loads all 25 CSVs from the `seeds/` symlink into your BigQuery dataset as tables.

### 6. Build the project

```bash
dbt build
```

This runs all models (staging → intermediate → marts) and their associated tests.

---

## Project structure

```
Claims-Denial-Intelligence-and-Prevention/
├── rcm/                        # dbt project root
│   ├── dbt_project.yml         # Project configuration
│   ├── packages.yml            # dbt package dependencies
│   ├── seeds -> ../Data/raw_data  # Symlink to raw CSVs
│   ├── models/
│   │   ├── staging/            # 1:1 cleaning of source tables
│   │   ├── intermediate/       # Business logic joins and transforms
│   │   └── marts/              # Final analytics tables (finance, ops, executive)
│   ├── analyses/               # Ad-hoc SQL (data profiling, etc.)
│   ├── macros/                 # Reusable SQL macros
│   └── tests/                  # Custom data tests
├── Data/
│   └── raw_data/               # 25 seed CSVs (tracked via Git LFS)
├── scripts/                    # Python data generation scripts
├── pyproject.toml              # Python dependencies
├── uv.lock                     # Locked dependency versions
└── TASKS.md                    # Project task tracker (90 tasks, 14 phases)
```

---

## Team collaboration workflow

We use a **feature-branch** workflow. No one pushes directly to `main`.

### Branching convention

```
main              ← production-ready, always passing
  └── feature/*   ← your working branches
```

Name your branches descriptively:

```bash
git checkout -b feature/staging-models-claims
git checkout -b feature/int-denial-analysis
git checkout -b fix/self-pay-filter
```

### Day-to-day workflow

```bash
# 1. Start from a fresh main
git checkout main
git pull origin main

# 2. Create your feature branch
git checkout -b feature/your-feature-name

# 3. Do your work — write models, run dbt build, iterate
dbt build --select staging.stg_claims+

# 4. Commit with a clear message
git add .
git commit -m "Add stg_claims and stg_denials staging models"

# 5. Push your branch
git push origin feature/your-feature-name

# 6. Open a Pull Request on GitHub
#    - Describe what you built and why
#    - Reference the task number from TASKS.md (e.g. "Closes task 6.1, 6.4")
#    - Request review from at least one teammate

# 7. After approval, merge to main (squash or merge commit — your choice)
```

### Code review checklist

When reviewing a teammate's PR, check for:

- Models compile: `dbt build --select <model_name>` passes
- Tests pass: no failures on `not_null`, `unique`, `relationships`, or custom tests
- Naming follows convention: `stg_`, `int_`, `fct_` prefixes
- YML documentation: new models have descriptions and column-level docs
- No hardcoded values: use `ref()` and `source()`, not raw table names

### Avoiding conflicts

- Each developer works in their own BigQuery dataset (`dbt_<name>`), so model builds never collide.
- Coordinate on shared files like `_sources.yml` — if two people edit it simultaneously, communicate in advance.
- Keep branches short-lived. Merge frequently to avoid drift from `main`.

---

## Useful dbt commands

```bash
# Run everything
dbt build

# Run a specific model and its downstream dependents
dbt build --select stg_claims+

# Run only tests
dbt test

# Generate and serve documentation
dbt docs generate
dbt docs serve

# Check source freshness
dbt source freshness

# Clean compiled artifacts
dbt clean
```

---

## Environment variables

If using a service account instead of OAuth (e.g. for CI), set:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your-service-account-key.json"
```

---

## Questions or issues?

Open an issue on the GitHub repo or reach out to the project lead (J — jubril.d.olalekan@gmail.com).
