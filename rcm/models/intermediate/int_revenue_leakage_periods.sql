WITH claim_spine AS (
    SELECT * FROM {{ ref('int_claim_financial_summary') }}
),

-- Use max service_date in the data as the reference point so the model
-- produces stable results during backfills and historical analysis.
reference_date AS (
    SELECT MAX(service_date) AS max_date FROM claim_spine
),

-- Define lookback periods as a static table; each claim is joined to all
-- periods it falls within so a single scan handles all three bands.
periods AS (
    SELECT  6 AS period_months, '6_months'  AS period_label
    UNION ALL
    SELECT 12 AS period_months, '12_months' AS period_label
    UNION ALL
    SELECT 24 AS period_months, '24_months' AS period_label
),

-- Fan out claims across every period band they belong to
claims_by_period AS (
    SELECT
        p.period_label,
        p.period_months,
        DATE_SUB(r.max_date, INTERVAL p.period_months MONTH)   AS period_start,
        r.max_date                                              AS period_end,
        c.claim_id,
        c.total_charge,
        c.total_allowed,
        c.total_collected,
        c.leakage_amount,
        c.denied_amount,
        c.is_denied,
        c.is_adjudicated,
        c.amount_recovered_via_appeal,
        c.had_successful_appeal
    FROM claim_spine c
    CROSS JOIN reference_date r
    CROSS JOIN periods p
    WHERE c.service_date >= DATE_SUB(r.max_date, INTERVAL p.period_months MONTH)
)

SELECT
    period_label,
    period_months,
    MIN(period_start)                                                           AS period_start,
    MIN(period_end)                                                             AS period_end,

    -- volume
    COUNT(claim_id)                                                             AS total_claims,
    COUNTIF(is_adjudicated)                                                     AS adjudicated_claims,
    COUNTIF(is_denied)                                                          AS denied_claims,
    COUNTIF(had_successful_appeal)                                              AS overturned_claims,

    -- financials
    ROUND(SUM(total_charge), 2)                                                 AS total_charges,
    ROUND(SUM(total_allowed), 2)                                                AS total_allowed,
    ROUND(SUM(total_collected), 2)                                              AS total_collected,

    -- leakage components
    ROUND(SUM(leakage_amount), 2)                                               AS gross_leakage,
    ROUND(SUM(denied_amount), 2)                                                AS total_denied_amount,
    ROUND(SUM(amount_recovered_via_appeal), 2)                                  AS total_appeal_recovery,

    -- net leakage after successful appeals
    ROUND(SUM(leakage_amount) - SUM(amount_recovered_via_appeal), 2)            AS net_leakage,

    -- rates
    ROUND(SAFE_DIVIDE(SUM(leakage_amount), SUM(total_allowed)), 4)              AS gross_leakage_rate,
    ROUND(SAFE_DIVIDE(SUM(total_collected), SUM(total_allowed)), 4)             AS collection_rate,
    ROUND(SAFE_DIVIDE(COUNTIF(is_denied), COUNT(claim_id)), 4)                  AS denial_rate

FROM claims_by_period
GROUP BY 1, 2
ORDER BY 2
