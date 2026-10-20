
WITH src_ref_lcd_ncd_policies AS (
    SELECT
        policy_id,
        policy_type,
        title,
        cpt_codes,
        covered_icd10,
        covered_conditions,
        non_covered_conditions,
        documentation_required,
        mac_region
    FROM {{ source('rcm_raw', 'ref_lcd_ncd_policies') }}
)

SELECT * FROM src_ref_lcd_ncd_policies
