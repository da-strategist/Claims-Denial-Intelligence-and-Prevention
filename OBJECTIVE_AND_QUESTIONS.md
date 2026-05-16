# Claims Denial Intelligence & Prevention Platform
## Objective & Analytical Questions

---

## Executive Summary

Hospitals across the US lose an average of 4.8% of net revenue to denied claims each year — an industry-wide problem costing providers $19.7 billion annually, $10.6 billion of which is pure administrative waste. The root cause is overwhelmingly preventable: 76% of denials stem from missing, inaccurate, or incomplete data submitted during the claims lifecycle.

**Our objective** is to build an analytics platform that gives hospital finance and operations leaders a clear, continuous view of where revenue is leaking, why claims are being denied, and what to fix — before the next claim goes out the door.

The platform serves three functions:

1. **Detect** — surface revenue leakage across payers, departments, providers, and procedure categories.
2. **Diagnose** — trace every denial back to the specific workflow step and root cause that created it.
3. **Prevent** — flag claims at risk of denial *before* submission, using the causal patterns in the data.

The target users are CFOs, COOs, VPs of Revenue Cycle, and Chief Revenue Officers at hospitals and health systems. The platform must answer their questions in language they act on — dollars at risk, denial rate trends, payer behavior, and department performance — not just tables and counts.

---

## Analytical Questions by Dashboard

### 1. Executive Summary Dashboard

These are the first questions a CFO or COO asks on Monday morning.

- What is our current denial rate, and how does it trend month-over-month?
- What is our clean claim rate, and is it improving or declining?
- How many days of revenue are sitting in accounts receivable on average?
- What is the first-pass resolution rate — how often are we getting paid on the first try?
- What is our net collection rate — are we collecting what we're owed?
- How much total revenue leakage have we experienced over the last 6, 12, and 24 months?
- Which single metric has deteriorated the most in the last quarter?

**Metrics to Derive:**

| Metric | Formula / Logic | Source Tables | Benchmark |
|--------|----------------|---------------|-----------|
| Denial Rate | denied claims ÷ total claims submitted | `fact_claims`, `fact_denials` | <5% |
| Clean Claim Rate | claims where `is_clean_claim = true` ÷ total claims | `fact_claims` | >95% |
| Avg Days in AR | mean of `days_in_ar` across open/resolved claims | `fact_claims` | <30 days |
| First-Pass Resolution Rate | claims paid without denial or rework ÷ total claims | `fact_claims`, `fact_denials` | >90% |
| Net Collection Rate | total_paid ÷ (total_allowed − contractual adjustments) | `fact_claims`, `fact_remittance` | >96% |
| Total Revenue Leakage | sum of denied amounts + underpayments + write-offs | `fact_denials`, `fact_remittance`, `dim_payer_contracts` | — |
| QoQ Metric Trend | current quarter value − prior quarter value for each KPI | All of the above, grouped by month/quarter | — |

---

### 2. Denial Root Cause Analysis Dashboard

This is where operations teams drill in to understand *why* claims are being denied.

- What are the top denial root cause categories, and what share of total denials does each represent?
- Which root causes are growing fastest quarter-over-quarter?
- How do denial causes break down by payer? Are specific payers driving specific categories?
- Which CPT code families generate the most denials — and is the issue coding, authorization, or eligibility?
- Which departments have the highest denial rates, and what root causes dominate in each?
- What percentage of our denials are classified as preventable?
- Which specific CARC and RARC codes appear most frequently, and what do they tell us about payer behavior?

**Metrics to Derive:**

| Metric | Formula / Logic | Source Tables |
|--------|----------------|---------------|
| Denial Count & Rate by Root Cause | count of denials per `root_cause_category` ÷ total denials | `fact_denials` |
| Root Cause QoQ Growth Rate | (current quarter count − prior quarter count) ÷ prior quarter count, per root cause | `fact_denials`, `fact_claims` (for service_date) |
| Denial Rate by Payer × Root Cause | denials per payer per root_cause_category ÷ total claims per payer | `fact_denials`, `fact_claims`, `dim_payers` |
| Denial Rate by CPT Family | denials joined to claim lines per `cpt_category` ÷ total claims per category | `fact_denials`, `fact_claim_lines`, `dim_cpt_codes` |
| Denial Rate by Department | denials per `department_id` ÷ total claims per department | `fact_denials`, `fact_claims`, `dim_departments` |
| Preventable Denial % | denials where `is_preventable = true` ÷ total denials | `fact_denials` |
| Top CARC/RARC Frequency | count of denials per `carc_code` and `rarc_code`, joined to descriptions | `fact_denials`, `ref_carc_codes`, `ref_rarc_codes` |

**Denial taxonomy**: Missing/Inaccurate Data (~24%), Prior Authorization (~31%), Coding Errors (~18%), Eligibility Issues (~20%), Medical Necessity (~5%), Duplicate Claims (~2%), Timely Filing (~1%)

---

### 3. Payer Scorecard Dashboard

This dashboard answers: which payers are costing us the most, and are they honoring their contracts?

- What is the denial rate by payer, and how does each compare to their contracted expectations?
- Which payers have the longest average days to payment?
- Which payers are underpaying relative to contracted rates — and by how much?
- Which payers require the most prior authorizations, and what is the PA denial rate for each?
- What is the appeal overturn rate by payer — who reverses when challenged, and who doesn't?
- Which payer-CPT combinations generate the most revenue variance (paid vs. billed)?
- Are any payers systematically worsening in denial rate or payment timing over time?

**Metrics to Derive:**

| Metric | Formula / Logic | Source Tables |
|--------|----------------|---------------|
| Denial Rate by Payer | denied claims per payer ÷ total claims per payer | `fact_denials`, `fact_claims`, `dim_payers` |
| Avg Days to Payment by Payer | mean of (`check_date` − `submission_date`) per payer | `fact_remittance`, `fact_claims`, `dim_payers` |
| Underpayment Amount by Payer | (`total_allowed` × `reimbursement_pct_of_charge`) − `total_paid`, summed per payer | `fact_remittance`, `dim_payer_contracts`, `fact_claim_lines` |
| PA Denial Rate by Payer | claims where `pa_required = true` and denied for PA reasons ÷ total PA-required claims per payer | `fact_claims`, `fact_denials`, `dim_payers` |
| Appeal Overturn Rate by Payer | appeals where `outcome = 'Overturned'` ÷ total appeals per payer | `fact_appeals`, `fact_denials`, `dim_payers` |
| Revenue Variance by Payer × CPT | `total_paid` − `total_allowed` per payer per cpt_category | `fact_remittance`, `fact_claim_lines`, `dim_payer_contracts` |
| Payer Trend (Denial Rate MoM) | denial rate per payer per month, trended over time | `fact_denials`, `fact_claims`, `dim_payers` |

**Context**: Medicare FFS typically has the lowest denial rate (7–9%) and fastest payment (14 days). Medicare Advantage has the highest denial rate (15–18%) and strictest PA requirements. Commercial payers vary widely by contract.

---

### 4. AR Aging Dashboard

This is the cash-flow lens — how much money is stuck in the pipeline, and where is the risk?

- What is the distribution of outstanding AR across aging buckets (0–30, 31–60, 61–90, 91–120, 120+ days)?
- What dollar amount is at risk in the 90+ day buckets?
- Which payers have the most claims stuck in late aging buckets?
- Which departments or service lines contribute the most to aged AR?
- How has the AR aging distribution shifted over the last 6 months — is it getting better or worse?
- What is the probability of collection at each aging bucket (expected recovery curve)?

**Metrics to Derive:**

| Metric | Formula / Logic | Source Tables |
|--------|----------------|---------------|
| AR Distribution by Bucket | count and sum of `total_charge` grouped by `days_in_ar` buckets (0–30, 31–60, 61–90, 91–120, 120+) | `fact_claims` |
| Dollar Amount at Risk (90+ days) | sum of `total_charge` for claims where `days_in_ar > 90` and status is not paid | `fact_claims` |
| AR by Payer | AR bucket distribution filtered/grouped by `payer_id` | `fact_claims`, `dim_payers` |
| AR by Department | AR bucket distribution filtered/grouped by `department_id` | `fact_claims`, `dim_departments` |
| AR Trend (6-month shift) | AR bucket distribution compared month-over-month using `service_date` | `fact_claims` |
| Expected Recovery Rate by Bucket | % of claims in each aging bucket that ultimately reached `status = 'Paid'` | `fact_claims` (historical outcomes) |
| Estimated Collectible AR | sum of (bucket dollar amount × bucket recovery rate) across all buckets | Derived from the above two metrics |

*See FOOTNOTES.md §1 for a plain-language explanation of the expected recovery curve.*

---

### 5. Workflow Bottleneck Analysis Dashboard

This is the operational diagnostic — which steps in the revenue cycle are breaking, and for whom?

- Across the 8 RCM workflow steps (registration → eligibility → PA → service → coding → charge capture → scrubbing → submission), which step has the highest failure rate?
- How do workflow failure rates differ by department?
- How do workflow failure rates differ by payer?
- Which workflow failures most frequently lead to denials? (i.e., the highest-leverage fix points)
- What is the charge lag distribution — how long does it take from service to claim submission, and which departments are slowest?
- Are there providers with consistently high failure rates at specific workflow steps (e.g., coding, documentation)?

**Metrics to Derive:**

| Metric | Formula / Logic | Source Tables |
|--------|----------------|---------------|
| Failure Rate per Workflow Step | events where `status = 'Fail'` ÷ total events, per `workflow_step` | `fact_workflow_events` |
| Failure Rate by Step × Department | failure rate per workflow step grouped by `department_id` | `fact_workflow_events`, `fact_claims`, `dim_departments` |
| Failure Rate by Step × Payer | failure rate per workflow step grouped by `payer_id` | `fact_workflow_events`, `fact_claims`, `dim_payers` |
| Failure-to-Denial Conversion Rate | claims with step failure that were subsequently denied ÷ claims with step failure | `fact_workflow_events`, `fact_denials` |
| Avg Charge Lag by Department | mean of `total_lag_days` grouped by department | `fact_charge_lag`, `fact_claims`, `dim_departments` |
| Charge Lag Bucket Distribution | count of claims per `charge_lag_bucket` | `fact_charge_lag` |
| Provider Failure Rate by Step | failure rate per workflow step grouped by `provider_id` | `fact_workflow_events`, `fact_claims`, `dim_providers` |
| Avg Step Duration | mean of `duration_minutes` per workflow step | `fact_workflow_events` |

**Design note**: Each claim in the dataset flows through all 8 workflow steps with pass/fail flags. Failures *cause* specific denial types — this causal chain is what makes root-cause attribution possible.

---

### 6. Pre-Submission Risk Flags Dashboard

This is the forward-looking, preventive layer — catching bad claims before they go out.

- Which claims currently in the pipeline have workflow failure patterns that predict denial?
- What is the estimated denial probability for claims about to be submitted, based on historical patterns?
- Which specific workflow failures (e.g., missing PA, eligibility not verified) are present on at-risk claims?
- How many claims could be rescued by intervening before submission?
- What is the estimated dollar value of preventable denials in the current submission queue?
- Which NCCI edits, MUE limits, or LCD/NCD policy violations are being caught at scrubbing vs. slipping through?

**Metrics to Derive:**

| Metric | Formula / Logic | Source Tables |
|--------|----------------|---------------|
| Denial Probability by Failure Pattern | historical denial rate for each combination of workflow step failures | `fact_workflow_events`, `fact_denials` |
| Flagged Claims Count | claims in holdout period with failure patterns that historically led to denial >50% of the time | `fact_workflow_events`, `fact_claims` (date-split) |
| Estimated Preventable Denial $ | sum of `total_charge` for flagged claims × historical denial rate for their failure pattern | `fact_claims`, `fact_workflow_events`, `fact_denials` |
| Rescue Opportunity | count of flagged claims where the failing step is correctable before submission | `fact_workflow_events` (step-level flags) |
| NCCI Edit Violations | claim line pairs matching `ref_ncci_ptp_edits` column_1/column_2 CPT combinations | `fact_claim_lines`, `ref_ncci_ptp_edits` |
| MUE Limit Violations | claim lines where `units > max_units_per_day` for that CPT | `fact_claim_lines`, `ref_mue_limits` |
| LCD/NCD Coverage Violations | claims where the ICD-10 + CPT combination is not in the covered set for the applicable policy | `fact_claims`, `fact_claim_lines`, `ref_lcd_ncd_policies` |

*See FOOTNOTES.md §3 for the design decision on retrospective vs. holdout simulation for this dashboard.*

---

### 7. Coding Accuracy & Provider Performance Dashboard

This dashboard helps coding managers and medical directors improve documentation and coding quality.

- What is the coding error rate by provider, specialty, and department?
- Which ICD-10 and CPT code combinations generate the most denials?
- Which providers have the lowest documentation completeness scores, and how does that correlate with denial rates?
- Are there code categories where upcoding or undercoding patterns are visible?
- What is the relationship between provider coding accuracy scores and clean claim rates?
- Which providers would benefit most from targeted coding education (highest error rate, highest claim volume)?

**Metrics to Derive:**

| Metric | Formula / Logic | Source Tables |
|--------|----------------|---------------|
| Coding Error Rate by Provider | denials where `root_cause_category = 'Coding Errors'` per provider ÷ total claims per provider | `fact_denials`, `fact_claims`, `dim_providers` |
| Coding Error Rate by Department | same logic grouped by `department_id` | `fact_denials`, `fact_claims`, `dim_departments` |
| Top Denial-Generating ICD-10 × CPT Pairs | count of denials grouped by `primary_icd10` × `cpt_code` from claim lines | `fact_denials`, `fact_claims`, `fact_claim_lines` |
| Documentation Completeness vs. Denial Rate | correlation of `documentation_completeness_score` with provider-level denial rate | `dim_providers`, `fact_denials`, `fact_claims` |
| Coding Accuracy vs. Clean Claim Rate | correlation of `coding_accuracy_score` with provider-level clean claim rate | `dim_providers`, `fact_claims` |
| Upcoding/Undercoding Indicator | paid amount vs. expected amount by CPT category per provider (significant variance flags) | `fact_claim_lines`, `ref_physician_fee_schedule`, `dim_providers` |
| Education Priority Score | providers ranked by (coding error count × avg charge per claim) — highest volume + highest error = top priority | `fact_denials`, `fact_claims`, `dim_providers` |

---

## Summary of Core Questions

At its heart, this platform answers five questions for hospital leadership:

1. **How much money are we losing?** — Total revenue leakage, by source and trend.
2. **Why are we losing it?** — Root causes traced to specific workflow failures, payers, departments, and providers.
3. **Who is responsible?** — Payer behavior, department performance, and provider-level accuracy.
4. **What should we fix first?** — Prioritized by dollar impact and preventability.
5. **How do we stop it from happening again?** — Pre-submission flags and workflow intervention points.

---

*Created: 2026-05-14*
*Source: PROJECT_INSTRUCTIONS.md and claims-denial-intelligence skill domain context*
