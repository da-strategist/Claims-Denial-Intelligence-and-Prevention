
WITH src_ref_mue_limits AS (
    SELECT
        mue_id,
        cast(cpt_code as string)            as cpt_code,
        cast(max_units_per_day as int64)    as max_units_per_day,
        adjudication_type,
        mue_rationale,
        cast(effective_date as date)        as effective_date,
        source
    FROM {{ source('rcm_raw', 'ref_mue_limits') }}
)

SELECT * FROM src_ref_mue_limits
