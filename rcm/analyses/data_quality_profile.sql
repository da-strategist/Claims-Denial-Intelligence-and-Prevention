-- ============================================================
-- Data Quality Profile — Claims Denial Intelligence Platform
-- Run date: 2026-05-04
-- All queries validated against rcm_data_raw in BigQuery
-- ============================================================


-- ------------------------------------------------------------
-- 1. ROW COUNTS (all 25 tables)
-- Results:
--   fact_claims              120,000
--   fact_claim_lines         303,139
--   fact_claim_status_history 276,337
--   fact_charge_lag          120,000
--   fact_encounters          120,000
--   fact_remittance          120,000
--   fact_scheduling          120,000
--   fact_workflow_events     960,000
--   fact_denials              22,348
--   fact_appeals               7,129
--   dim_patients              15,000
--   dim_providers                 85
--   dim_payers                    12
--   dim_departments               14
--   dim_facilities                 7
--   dim_cpt_codes                 61
--   dim_icd10_codes               80
--   dim_payer_contracts          143
--   ref_carc_codes                31
--   ref_rarc_codes                12
--   ref_lcd_ncd_policies          15
--   ref_mue_limits                60
--   ref_ncci_ptp_edits            43
--   ref_nppes_providers           85
--   ref_physician_fee_schedule    60
-- ------------------------------------------------------------

SELECT
    'dim_patients'               AS table_name, COUNT(*) AS row_count FROM {{ source('rcm_raw', 'dim_patients') }}
UNION ALL SELECT 'dim_providers',               COUNT(*) FROM {{ source('rcm_raw', 'dim_providers') }}
UNION ALL SELECT 'dim_payers',                  COUNT(*) FROM {{ source('rcm_raw', 'dim_payers') }}
UNION ALL SELECT 'dim_departments',             COUNT(*) FROM {{ source('rcm_raw', 'dim_departments') }}
UNION ALL SELECT 'dim_facilities',              COUNT(*) FROM {{ source('rcm_raw', 'dim_facilities') }}
UNION ALL SELECT 'dim_cpt_codes',               COUNT(*) FROM {{ source('rcm_raw', 'dim_cpt_codes') }}
UNION ALL SELECT 'dim_icd10_codes',             COUNT(*) FROM {{ source('rcm_raw', 'dim_icd10_codes') }}
UNION ALL SELECT 'dim_payer_contracts',         COUNT(*) FROM {{ source('rcm_raw', 'dim_payer_contracts') }}
UNION ALL SELECT 'fact_claims',                 COUNT(*) FROM {{ source('rcm_raw', 'fact_claims') }}
UNION ALL SELECT 'fact_denials',                COUNT(*) FROM {{ source('rcm_raw', 'fact_denials') }}
UNION ALL SELECT 'fact_appeals',                COUNT(*) FROM {{ source('rcm_raw', 'fact_appeals') }}
UNION ALL SELECT 'fact_claim_lines',            COUNT(*) FROM {{ source('rcm_raw', 'fact_claim_lines') }}
UNION ALL SELECT 'fact_claim_status_history',   COUNT(*) FROM {{ source('rcm_raw', 'fact_claim_status_history') }}
UNION ALL SELECT 'fact_charge_lag',             COUNT(*) FROM {{ source('rcm_raw', 'fact_charge_lag') }}
UNION ALL SELECT 'fact_encounters',             COUNT(*) FROM {{ source('rcm_raw', 'fact_encounters') }}
UNION ALL SELECT 'fact_remittance',             COUNT(*) FROM {{ source('rcm_raw', 'fact_remittance') }}
UNION ALL SELECT 'fact_scheduling',             COUNT(*) FROM {{ source('rcm_raw', 'fact_scheduling') }}
UNION ALL SELECT 'fact_workflow_events',        COUNT(*) FROM {{ source('rcm_raw', 'fact_workflow_events') }}
UNION ALL SELECT 'ref_carc_codes',              COUNT(*) FROM {{ source('rcm_raw', 'ref_carc_codes') }}
UNION ALL SELECT 'ref_rarc_codes',              COUNT(*) FROM {{ source('rcm_raw', 'ref_rarc_codes') }}
UNION ALL SELECT 'ref_lcd_ncd_policies',        COUNT(*) FROM {{ source('rcm_raw', 'ref_lcd_ncd_policies') }}
UNION ALL SELECT 'ref_mue_limits',              COUNT(*) FROM {{ source('rcm_raw', 'ref_mue_limits') }}
UNION ALL SELECT 'ref_ncci_ptp_edits',          COUNT(*) FROM {{ source('rcm_raw', 'ref_ncci_ptp_edits') }}
UNION ALL SELECT 'ref_nppes_providers',         COUNT(*) FROM {{ source('rcm_raw', 'ref_nppes_providers') }}
UNION ALL SELECT 'ref_physician_fee_schedule',  COUNT(*) FROM {{ source('rcm_raw', 'ref_physician_fee_schedule') }}
ORDER BY 1;


-- ------------------------------------------------------------
-- 2. FACT_CLAIMS KEY METRICS
-- Results:
--   Date range       : 2024-01-01 → 2025-12-31 (2 years)
--   Distinct statuses: 2 (Paid, Denied)
--   Distinct payers  : 12
--   Distinct depts   : 14
--   Avg charge       : $3,730.44
--   Avg paid         : $2,326.08
--   Avg days in AR   : 30.75
--   Clean claims     : 81,469 / 120,000 = 67.9%
-- ------------------------------------------------------------

SELECT
    MIN(service_date)                                       AS min_service_date,
    MAX(service_date)                                       AS max_service_date,
    COUNT(DISTINCT status)                                  AS distinct_statuses,
    COUNT(DISTINCT payer_id)                                AS distinct_payers,
    COUNT(DISTINCT department_id)                           AS distinct_departments,
    ROUND(AVG(total_charge), 2)                             AS avg_charge,
    ROUND(AVG(total_paid), 2)                               AS avg_paid,
    ROUND(AVG(days_in_ar), 2)                               AS avg_days_in_ar
FROM {{ source('rcm_raw', 'fact_claims') }};


-- ------------------------------------------------------------
-- 3. CLAIM STATUS DISTRIBUTION
-- Results:
--   Paid   : 97,652  (81.38%)
--   Denied : 22,348  (18.62%)
-- ------------------------------------------------------------

SELECT
    status,
    COUNT(*)                                    AS claim_count,
    ROUND(COUNT(*) / 120000.0 * 100, 2)        AS pct_of_total
FROM {{ source('rcm_raw', 'fact_claims') }}
GROUP BY status
ORDER BY claim_count DESC;


-- ------------------------------------------------------------
-- 4. DENIAL ROOT CAUSE DISTRIBUTION
-- Results:
--   Coding Errors           : 7,012  (31.4%)  $27.8M denied
--   Prior Authorization     : 5,177  (23.2%)  $23.3M denied
--   Missing/Inaccurate Data : 4,179  (18.7%)  $15.7M denied
--   Eligibility             : 3,903  (17.5%)  $14.6M denied
--   Medical Necessity       : 1,164   (5.2%)   $4.3M denied
--   Duplicate               :   640   (2.9%)   $2.3M denied
--   Timely Filing           :   273   (1.2%)   $1.1M denied
-- ------------------------------------------------------------

SELECT
    root_cause_category,
    COUNT(*)                                    AS denial_count,
    ROUND(COUNT(*) / 22348.0 * 100, 2)         AS pct_of_denials,
    ROUND(SUM(denial_amount), 2)                AS total_denied_amount,
    ROUND(AVG(days_to_denial), 1)               AS avg_days_to_denial
FROM {{ source('rcm_raw', 'fact_denials') }}
GROUP BY root_cause_category
ORDER BY denial_count DESC;


-- ------------------------------------------------------------
-- 5. SELF-PAY DENIAL BUG CHECK
-- Finding: CLEAN — Self-Pay patients have 0 denials (3,376 claims)
-- Self-Pay patients should never receive insurance denials since
-- no payer is involved. This is correctly represented in the data.
-- ------------------------------------------------------------

SELECT
    p.payer_type,
    COUNT(DISTINCT c.claim_id)      AS total_claims,
    COUNT(DISTINCT d.denial_id)     AS denials
FROM {{ source('rcm_raw', 'fact_claims') }} c
JOIN {{ source('rcm_raw', 'dim_payers') }} p
    ON c.payer_id = p.payer_id
LEFT JOIN {{ source('rcm_raw', 'fact_denials') }} d
    ON c.claim_id = d.claim_id
WHERE p.payer_type = 'Self-Pay'
GROUP BY p.payer_type;


-- ------------------------------------------------------------
-- 6. REFERENTIAL INTEGRITY CHECKS
-- Results: 0 violations across all 6 key FK relationships
--   claims → patients       : 0
--   claims → providers      : 0
--   claims → payers         : 0
--   denials → claims        : 0
--   appeals → denials       : 0
--   claim_lines → claims    : 0
-- ------------------------------------------------------------

SELECT 'claims missing patient'       AS check_name, COUNT(*) AS violations
FROM {{ source('rcm_raw', 'fact_claims') }} c
LEFT JOIN {{ source('rcm_raw', 'dim_patients') }} p ON c.patient_id = p.patient_id
WHERE p.patient_id IS NULL

UNION ALL
SELECT 'claims missing provider',     COUNT(*)
FROM {{ source('rcm_raw', 'fact_claims') }} c
LEFT JOIN {{ source('rcm_raw', 'dim_providers') }} p ON c.provider_id = p.provider_id
WHERE p.provider_id IS NULL

UNION ALL
SELECT 'claims missing payer',        COUNT(*)
FROM {{ source('rcm_raw', 'fact_claims') }} c
LEFT JOIN {{ source('rcm_raw', 'dim_payers') }} p ON c.payer_id = p.payer_id
WHERE p.payer_id IS NULL

UNION ALL
SELECT 'denials missing claim',       COUNT(*)
FROM {{ source('rcm_raw', 'fact_denials') }} d
LEFT JOIN {{ source('rcm_raw', 'fact_claims') }} c ON d.claim_id = c.claim_id
WHERE c.claim_id IS NULL

UNION ALL
SELECT 'appeals missing denial',      COUNT(*)
FROM {{ source('rcm_raw', 'fact_appeals') }} a
LEFT JOIN {{ source('rcm_raw', 'fact_denials') }} d ON a.denial_id = d.denial_id
WHERE d.denial_id IS NULL

UNION ALL
SELECT 'claim_lines missing claim',   COUNT(*)
FROM {{ source('rcm_raw', 'fact_claim_lines') }} l
LEFT JOIN {{ source('rcm_raw', 'fact_claims') }} c ON l.claim_id = c.claim_id
WHERE c.claim_id IS NULL;
