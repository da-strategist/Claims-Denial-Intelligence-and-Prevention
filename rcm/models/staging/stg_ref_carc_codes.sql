
WITH src_ref_carc_codes AS (
    SELECT
        cast(carc_code as STRING) as carc_code,
        description,
        group_code
    FROM {{ source('rcm_raw', 'ref_carc_codes') }}
)

SELECT * FROM src_ref_carc_codes
