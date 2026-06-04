
WITH src_ref_rarc_codes AS (
    SELECT
        rarc_code,
        description
    FROM {{ source('rcm_raw', 'ref_rarc_codes') }}
)

SELECT * FROM src_ref_rarc_codes
