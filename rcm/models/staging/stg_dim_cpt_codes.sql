
WITH src_dim_cpt_codes AS (
    SELECT
        cast(cpt_code as string)                    as cpt_code,
        description,
        category,
        round(cast(standard_charge as numeric), 2)  as standard_charge,
        primary_department,
        billing_type
    FROM {{ source('rcm_raw', 'dim_cpt_codes') }}
)

SELECT * FROM src_dim_cpt_codes
