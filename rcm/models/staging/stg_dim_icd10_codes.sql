
WITH src_dim_icd10_codes AS (
    SELECT
        cast(icd10_code as string)                      as icd10_code,
        description,
        body_system,
        round(cast(relative_frequency as numeric), 4)  as relative_frequency,
        acuity_type
    FROM {{ source('rcm_raw', 'dim_icd10_codes') }}
)

SELECT * FROM src_dim_icd10_codes
