
WITH src_remittance AS (
    SELECT
        remittance_id,
        claim_id,
        payer_id,
        cast(check_date as date)                    as check_date,
        cast(check_number as string)                as check_number,
        round(cast(total_charge as numeric), 2)     as total_charge,
        round(cast(total_allowed as numeric), 2)    as total_allowed,
        round(cast(total_paid as numeric), 2)       as total_paid,
        round(cast(adjustment_amount as numeric), 2) as adjustment_amount,
        adjudication_status,
        cast(carc_code as string)                   as carc_code,
        cast(rarc_code as string)                   as rarc_code
    FROM {{ source('rcm_raw', 'fact_remittance') }}
)

, cleaned_remittance AS (
    SELECT
        remittance_id,
        claim_id,
        payer_id,
        check_date,
        check_number,
        total_charge,
        total_allowed,
        total_paid,
        adjustment_amount,
        round(total_paid - total_allowed, 2)    as pymt_variance,
        CASE
            WHEN total_paid < total_allowed THEN 'underpaid'
            WHEN total_paid > total_allowed THEN 'overpaid'
            WHEN total_paid = total_allowed THEN 'full payment'
        END                                     as pymt_variance_type,
        adjudication_status,
        carc_code,
        rarc_code
    FROM src_remittance
)

SELECT * FROM cleaned_remittance
