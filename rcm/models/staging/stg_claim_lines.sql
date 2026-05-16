

    WITH src_claim_lines as 
    (
        SELECT 
            line_id,
            claim_id,
            line_number,
            cast(cpt_code as string) as cpt_code,
            cpt_category,
            cast(modifier as STRING) as cpt_modifier,
            units,
            round(cast(charge_amount as numeric),2) as charge_amount,
            round(cast(allowed_amount as numeric),2) as allowed_amount,
            round(cast(paid_amount as numeric),2) as paid_amount,
            round((paid_amount) - (allowed_amount),2) as pymt_variance,
            icd10_pointer as dx_code
        FROM {{source('rcm_raw', 'fact_claim_lines')}}

    ), cleaned_claim_lines as 
    (
        SELECT 
            line_id,
            claim_id,
            line_number,
            dx_code,
            cpt_category,
            cpt_code,
            cpt_modifier,                
            units,
            charge_amount,
            allowed_amount,
            paid_amount,
            pymt_variance,
            CASE WHEN pymt_variance < 0 THEN 'underpaid' 
                WHEN pymt_variance > 0 THEN 'overpaid'
                WHEN pymt_variance = 0 THEN 'full payment'
                END AS pymt_variance_type
        FROM src_claim_lines
    )
        SELECT * FROM cleaned_claim_lines