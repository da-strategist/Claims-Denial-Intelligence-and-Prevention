
WITH denials AS (
    SELECT * FROM {{ ref('stg_fact_denials') }}
)

, claims AS (
    SELECT
        claim_id,
        payer_id,
        department_id,
        provider_id,
        total_charge,
        claim_type,
        service_date,
        submission_date,
        primary_icd10,
        pa_required,
        pa_obtained
    FROM {{ ref('stg_fact_claims') }}
)

, carc AS (
    SELECT * FROM {{ ref('stg_ref_carc_codes') }}
)

, rarc AS (
    SELECT * 
    FROM {{ ref('stg_ref_rarc_codes') }}
)
, int_denial_analysis as 
(
    SELECT
        -- denial identifiers
        d.denial_id,
        d.claim_id,
        d.payer_id,

        -- denial dates & dimensions
        d.denial_date,
        date_trunc(d.denial_date, month)        as denial_month,
        date_trunc(d.denial_date, quarter)      as denial_quarter,
        ---extract(year from d.denial_date)        as denial_year,

        -- denial financials
        d.denial_amount,

        -- claim context
        c.department_id,
        c.provider_id,
        ---c.total_charge                          as claim_total_charge,
        ---c.claim_type,
        --c.service_date,
        ---c.submission_date,
        ---c.primary_icd10,
        c.pa_required,
        c.pa_obtained

    FROM denials d
    LEFT JOIN claims c  ON d.claim_id  = c.claim_id
    LEFT JOIN carc      ON d.carc_code = carc.carc_code
    LEFT JOIN rarc      ON d.rarc_code = rarc.rarc_code
)
    SELECT * FROM int_denial_analysis
