
WITH src_dim_payers AS (
    SELECT
        payer_id,
        payer_name,
        payer_type,
        round(cast(market_share as numeric), 4)     as market_share,
        round(cast(denial_rate as numeric), 4)      as denial_rate,
        cast(avg_days_to_pay as int64)              as avg_days_to_pay,
        round(cast(pa_strictness as numeric), 4)    as pa_strictness,
        policy_prefix,
        status
    FROM {{ source('rcm_raw', 'dim_payers') }}
)

SELECT * FROM src_dim_payers
