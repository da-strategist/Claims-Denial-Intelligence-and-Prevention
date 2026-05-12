
WITH src_denials as 
    (
        SELECT 
            denial_id,
            claim_id,
            payer_id,
            cast(denial_date as date) as denial_date,
            root_cause_category,
            carc_code,
            rarc_code,
            round(cast(denial_amount as numeric), 2) as denial_amount,
            workflow_failure_point,
            is_preventable,
            denial_reason_text, 
            days_to_denial

        FROM {{source ('rcm_raw', 'fact_denials')}} d
    )

, cleaned_denial_reason as 

    (
        SELECT
            denial_id,
            claim_id,
            payer_id,
            denial_date,
            root_cause_category,
            TRIM(SUBSTRING(denial_reason_text, STRPOS(denial_reason_text, ':') +1)) as denial_reason,
            carc_code,
            rarc_code,
            denial_amount,
            workflow_failure_point,
            is_preventable,
            days_to_denial
        FROM src_denials d
    )

SELECT * FROM cleaned_denial_reason