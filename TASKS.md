# Claims Denial Intelligence Platform — Task List

> Tracked daily by the `healthcare-rcm-daily-brief` scheduled task.  
> Status key: `[ ]` Pending | `[~]` In Progress | `[x]` Completed

---

## Phase 1: Environment & Project Setup

- [ ] 1.1 Install `uv` package installer
- [ ] 1.2 Create Python virtual environment with `uv` (Python 3.11+)
- [ ] 1.3 Install core packages: dbt-core, dbt-duckdb, duckdb, pandas, python-dotenv
- [ ] 1.4 Install supplementary packages: requests (WHO API), openpyxl, great_expectations (optional)
- [ ] 1.5 Generate `pyproject.toml` and lock dependencies with `uv`
- [ ] 1.6 Initialize git repository and create `.gitignore`
- [ ] 1.7 Create project directory structure (dbt_project/, docs/, dashboards/, tests/)

## Phase 2: dbt Project Initialization

- [ ] 2.1 Run `dbt init` to scaffold dbt project (claims_denial_intelligence)
- [ ] 2.2 Configure `dbt_project.yml` (project name, profile, model paths, seed paths)
- [ ] 2.3 Configure `profiles.yml` for DuckDB (local dev warehouse)
- [ ] 2.4 Set up dbt directory structure (staging/, intermediate/, marts/)
- [ ] 2.5 Create `packages.yml` (dbt_utils, dbt_expectations, codegen)
- [ ] 2.6 Run `dbt deps` to install dbt packages

## Phase 3: Data Ingestion (dbt seed)

- [ ] 3.1 Copy/symlink raw CSVs into dbt `seeds/` directory
- [ ] 3.2 Create `_seeds.yml` schema file with column types and descriptions
- [ ] 3.3 Configure seed properties in `dbt_project.yml` (quote columns, column types)
- [ ] 3.4 Run `dbt seed` to load all 25 CSVs into DuckDB
- [ ] 3.5 Validate row counts match expected (fact_claims: 120K, fact_denials: ~22.3K, etc.)
- [ ] 3.6 Run `dbt seed --show` to verify sample data loads correctly

## Phase 4: Source Configuration & Documentation

- [ ] 4.1 Create `_sources.yml` with full source definitions for all 25 tables
- [ ] 4.2 Add column-level descriptions to source definitions
- [ ] 4.3 Add source freshness checks (loaded_at_field where applicable)
- [ ] 4.4 Regenerate DATA_DICTIONARY.md from source definitions
- [ ] 4.5 Run `dbt source freshness` to validate configuration

## Phase 5: Data Profiling & Quality Assessment

- [ ] 5.1 Profile dimension tables (row counts, null rates, cardinality)
- [ ] 5.2 Profile fact tables (distributions, date ranges, key metrics)
- [ ] 5.3 Identify and document the Self-Pay denial bug (self-pay patients should have 0 denials)
- [ ] 5.4 Check referential integrity (foreign keys between fact and dim tables)
- [ ] 5.5 Document data quality findings and decisions

## Phase 6: Staging Models

- [ ] 6.1 `stg_claims.sql` — clean fact_claims (rename, cast, filter)
- [ ] 6.2 `stg_claim_lines.sql` — clean fact_claim_lines
- [ ] 6.3 `stg_remittance.sql` — clean fact_remittance
- [ ] 6.4 `stg_denials.sql` — clean fact_denials
- [ ] 6.5 `stg_appeals.sql` — clean fact_appeals
- [ ] 6.6 `stg_workflow_events.sql` — clean fact_workflow_events
- [ ] 6.7 `stg_patients.sql` — clean dim_patients
- [ ] 6.8 `stg_providers.sql` — clean dim_providers
- [ ] 6.9 `stg_payers.sql` — clean dim_payers
- [ ] 6.10 `stg_departments.sql` — clean dim_departments
- [ ] 6.11 `stg_facilities.sql` — clean dim_facilities
- [ ] 6.12 `stg_payer_contracts.sql` — clean dim_payer_contracts
- [ ] 6.13 `stg_charge_lag.sql` — clean fact_charge_lag
- [ ] 6.14 `stg_encounters.sql` — clean fact_encounters
- [ ] 6.15 `stg_scheduling.sql` — clean fact_scheduling
- [ ] 6.16 `stg_claim_status_history.sql` — clean fact_claim_status_history
- [ ] 6.17 Create `_stg.yml` schema files with tests (not_null, unique, accepted_values, relationships)
- [ ] 6.18 Fix Self-Pay denial issue at staging layer (filter out self-pay denials)
- [ ] 6.19 Run `dbt build --select staging` and resolve errors

## Phase 7: Intermediate Models

- [ ] 7.1 `int_claims_enriched.sql` — join claims + patient + provider + payer + department
- [ ] 7.2 `int_denial_analysis.sql` — denials + root cause + workflow failure point + CARC/RARC
- [ ] 7.3 `int_workflow_summary.sql` — pivot workflow events to one row per claim (8 step pass/fail)
- [ ] 7.4 `int_ar_aging.sql` — claims bucketed by AR days (0-30, 31-60, 61-90, 91-120, 120+)
- [ ] 7.5 `int_charge_lag_analysis.sql` — service-to-submission timing with lag buckets
- [ ] 7.6 `int_remittance_analysis.sql` — payment vs. billed, underpayment detection
- [ ] 7.7 Create `_int.yml` schema files with tests
- [ ] 7.8 Run `dbt build --select intermediate` and resolve errors

## Phase 8: Mart Models — Finance

- [ ] 8.1 `fct_revenue_leakage.sql` — quantify leakage by category, payer, department
- [ ] 8.2 `fct_ar_aging_buckets.sql` — AR aging distribution with dollar amounts at risk
- [ ] 8.3 `fct_underpayments.sql` — contracted rate vs. paid, variance by payer and CPT
- [ ] 8.4 Create `_finance.yml` schema files with tests

## Phase 9: Mart Models — Operations

- [ ] 9.1 `fct_denial_root_cause.sql` — denial breakdown by root cause, payer, CPT, dept
- [ ] 9.2 `fct_workflow_bottlenecks.sql` — failure rates per workflow step, by dept and payer
- [ ] 9.3 `fct_clean_claim_rate.sql` — clean claim % by payer, dept, provider, trending
- [ ] 9.4 `fct_coding_accuracy.sql` — coding error rates by provider, specialty, code category
- [ ] 9.5 Create `_operations.yml` schema files with tests

## Phase 10: Mart Models — Executive

- [ ] 10.1 `fct_kpi_summary.sql` — top-line KPIs (denial rate, CCR, days in AR, NCR, FPRR)
- [ ] 10.2 `fct_payer_scorecard.sql` — per-payer performance metrics and benchmarks
- [ ] 10.3 `fct_department_performance.sql` — department-level denial, revenue, clean claim metrics
- [ ] 10.4 Create `_executive.yml` schema files with tests

## Phase 11: dbt Testing & Validation

- [ ] 11.1 Run full `dbt build` end-to-end and resolve all errors
- [ ] 11.2 Add custom generic tests (e.g., denial_rate_within_range, no_self_pay_denials)
- [ ] 11.3 Add dbt_expectations tests for distribution checks
- [ ] 11.4 Validate mart outputs against known metrics (18% denial rate, ~76% CCR, etc.)
- [ ] 11.5 Run `dbt test` — all tests passing

## Phase 12: Documentation & dbt Docs

- [ ] 12.1 Add model descriptions to all yml files
- [ ] 12.2 Create `overview.md` for dbt docs site
- [ ] 12.3 Run `dbt docs generate` and review lineage graph
- [ ] 12.4 Finalize DATA_DICTIONARY.md with all models documented
- [ ] 12.5 Update PROJECT_INSTRUCTIONS.md with completed state

## Phase 13: External Data Integration (Stretch)

- [ ] 13.1 Build Python script to pull ICD-10 codes from WHO API
- [ ] 13.2 Build Python script to pull CPT/fee schedule from CMS
- [ ] 13.3 Create dbt models to replace static dim_icd10_codes and ref_physician_fee_schedule
- [ ] 13.4 Validate integrated data matches expected structure

## Phase 14: Visualization Prep (Tableau)

- [ ] 14.1 Export mart tables to Tableau-friendly format (Parquet or DuckDB connection)
- [ ] 14.2 Create Tableau data source connections
- [ ] 14.3 Build Executive Summary dashboard
- [ ] 14.4 Build Denial Root Cause Analysis dashboard
- [ ] 14.5 Build Payer Scorecard dashboard
- [ ] 14.6 Build AR Aging dashboard
- [ ] 14.7 Build Workflow Bottleneck Analysis dashboard

---

## Summary

| Phase | Tasks | Status |
|-------|-------|--------|
| 1. Environment Setup | 7 | Pending |
| 2. dbt Init | 6 | Pending |
| 3. Data Ingestion | 6 | Pending |
| 4. Source Config | 5 | Pending |
| 5. Data Profiling | 5 | Pending |
| 6. Staging Models | 19 | Pending |
| 7. Intermediate Models | 8 | Pending |
| 8. Finance Marts | 4 | Pending |
| 9. Operations Marts | 5 | Pending |
| 10. Executive Marts | 4 | Pending |
| 11. Testing | 5 | Pending |
| 12. Documentation | 5 | Pending |
| 13. External APIs | 4 | Pending |
| 14. Visualization | 7 | Pending |
| **Total** | **90** | **Pending** |

---

*Created: 2026-05-04*  
*Last updated: 2026-05-04*
