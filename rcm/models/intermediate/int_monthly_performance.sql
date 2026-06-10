WITH monthly_agg AS (
    SELECT
        service_month                                                                           AS month_date,

        -- volume denominators
        COUNT(claim_id)                                                                         AS total_claims,
        COUNTIF(is_adjudicated)                                                                 AS adjudicated_claims,
        COUNTIF(status = 'paid')                                                                AS paid_claims,

        -- KPI numerators
        COUNTIF(is_denied)                                                                      AS denied_claims,
        COUNTIF(is_clean_claim)                                                                 AS clean_claims,
        COUNTIF(is_first_pass_paid)                                                             AS first_pass_paid_claims,

        -- financials
        ROUND(SUM(total_charge), 2)                                                             AS total_charges,
        ROUND(SUM(total_allowed), 2)                                                            AS total_allowed,
        ROUND(SUM(total_collected), 2)                                                          AS total_collected,
        ROUND(SUM(leakage_amount), 2)                                                           AS total_leakage,
        ROUND(SUM(amount_recovered_via_appeal), 2)                                              AS total_appeal_recovery,

        -- AR: only include adjudicated claims with a recorded days_in_ar value
        ROUND(AVG(IF(is_adjudicated AND days_in_ar IS NOT NULL, CAST(days_in_ar AS FLOAT64), NULL)), 1) AS avg_days_in_ar

    FROM {{ ref('int_claim_financial_summary') }}
    GROUP BY 1
),

with_rates AS (
    SELECT
        month_date,
        total_claims,
        adjudicated_claims,
        paid_claims,
        denied_claims,
        clean_claims,
        first_pass_paid_claims,
        total_charges,
        total_allowed,
        total_collected,
        total_leakage,
        total_appeal_recovery,
        avg_days_in_ar,

        -- denial rate: denied claims / all submitted claims
        ROUND(SAFE_DIVIDE(denied_claims, total_claims), 4)                                      AS denial_rate,

        -- clean claim rate: clean claims / all submitted claims
        ROUND(SAFE_DIVIDE(clean_claims, total_claims), 4)                                       AS clean_claim_rate,

        -- first-pass resolution rate: paid-without-denial / all adjudicated claims
        ROUND(SAFE_DIVIDE(first_pass_paid_claims, adjudicated_claims), 4)                       AS first_pass_resolution_rate,

        -- net collection rate: total collected / total allowed (contractual ceiling)
        ROUND(SAFE_DIVIDE(total_collected, total_allowed), 4)                                   AS net_collection_rate

    FROM monthly_agg
),

with_mom AS (
    SELECT
        *,
        LAG(denial_rate)                OVER (ORDER BY month_date)                              AS prior_month_denial_rate,
        LAG(clean_claim_rate)           OVER (ORDER BY month_date)                              AS prior_month_clean_claim_rate,
        LAG(first_pass_resolution_rate) OVER (ORDER BY month_date)                              AS prior_month_fprr,
        LAG(net_collection_rate)        OVER (ORDER BY month_date)                              AS prior_month_ncr,
        LAG(avg_days_in_ar)             OVER (ORDER BY month_date)                              AS prior_month_avg_days_in_ar,
        LAG(total_leakage)              OVER (ORDER BY month_date)                              AS prior_month_leakage
    FROM with_rates
)

SELECT
    *,

    -- MoM absolute deltas
    -- Note: for denial_rate and days_in_ar a negative delta means improvement;
    --       for clean_claim_rate, fprr, ncr a positive delta means improvement.
    ROUND(denial_rate - prior_month_denial_rate, 4)                                             AS denial_rate_mom_delta,
    ROUND(clean_claim_rate - prior_month_clean_claim_rate, 4)                                   AS clean_claim_rate_mom_delta,
    ROUND(first_pass_resolution_rate - prior_month_fprr, 4)                                     AS fprr_mom_delta,
    ROUND(net_collection_rate - prior_month_ncr, 4)                                             AS ncr_mom_delta,
    ROUND(avg_days_in_ar - prior_month_avg_days_in_ar, 1)                                       AS days_in_ar_mom_delta,
    ROUND(total_leakage - prior_month_leakage, 2)                                               AS leakage_mom_delta

FROM with_mom
