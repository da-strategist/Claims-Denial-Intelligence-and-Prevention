WITH claims AS (
    SELECT * FROM {{ ref('stg_fact_claims') }}
),

denials_agg AS (
    SELECT
        claim_id,
        COUNT(denial_id)                                                        AS denial_count,
        MIN(denial_date)                                                        AS first_denial_date,
        SUM(denial_amount)                                                      AS total_denied_amount,
        SUM(CAST(is_preventable AS INT64))                                      AS preventable_denial_count
    FROM {{ ref('stg_fact_denials') }}
    GROUP BY 1
),

appeals_agg AS (
    SELECT
        claim_id,
        COUNT(appeal_id)                                                        AS appeal_count,
        COUNTIF(is_overturned)                                                  AS overturned_count,
        SUM(IF(is_overturned, overturn_amount, 0))                             AS amount_recovered
    FROM {{ ref('stg_fact_appeals') }}
    GROUP BY 1
)

SELECT
    -- identifiers
    c.claim_id,
    c.patient_id,
    c.provider_id,
    c.payer_id,
    c.facility_id,
    c.department_id,

    -- dates
    c.service_date,
    c.submission_date,
    DATE_TRUNC(c.service_date, MONTH)                                           AS service_month,
    DATE_TRUNC(c.service_date, QUARTER)                                         AS service_quarter,
    EXTRACT(YEAR FROM c.service_date)                                           AS service_year,

    -- financials
    c.total_charge,
    c.total_allowed,
    c.total_paid,
    c.amount_pt_charged,
    c.total_collected,

    -- leakage: gap between contractually owed and actually collected, for closed claims only
    CASE
        WHEN c.total_allowed > 0
             AND c.status IN ('paid', 'denied', 'closed', 'written_off')
        THEN GREATEST(c.total_allowed - c.total_collected, 0)
        ELSE 0
    END                                                                         AS leakage_amount,

    -- claim status and quality flags
    c.status,
    c.status IN ('paid', 'denied', 'closed', 'written_off')                    AS is_adjudicated,
    CAST(c.is_clean_claim AS BOOL)                                              AS is_clean_claim,
    c.bill_match_status                                                         AS is_fully_collected,
    c.days_in_ar,

    -- denial flags
    COALESCE(d.denial_count, 0) > 0                                            AS is_denied,
    COALESCE(d.denial_count, 0)                                                 AS denial_count,
    COALESCE(d.total_denied_amount, 0)                                          AS denied_amount,
    COALESCE(d.preventable_denial_count, 0)                                     AS preventable_denial_count,
    d.first_denial_date,

    -- first-pass resolution: paid on initial submission with no denial on record
    c.status = 'paid' AND COALESCE(d.denial_count, 0) = 0                      AS is_first_pass_paid,

    -- appeal outcomes
    COALESCE(a.appeal_count, 0)                                                 AS appeal_count,
    COALESCE(a.overturned_count, 0)                                             AS overturned_count,
    COALESCE(a.overturned_count, 0) > 0                                         AS had_successful_appeal,
    COALESCE(a.amount_recovered, 0)                                             AS amount_recovered_via_appeal,

    -- metadata
    c.claim_type,
    c.service_point,
    c.pa_required,
    c.pa_obtained,
    c.service_to_submission_days

FROM claims c
LEFT JOIN denials_agg d     ON c.claim_id = d.claim_id
LEFT JOIN appeals_agg a     ON c.claim_id = a.claim_id
