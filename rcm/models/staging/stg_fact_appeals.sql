
WITH src_appeals as 

    (
        SELECT 
            appeal_id, 
            denial_id,
            claim_id,
            cast(appeal_date as date) as appeal_date,
            appeal_level, 
            TRIM(SUBSTR(appeal_reason, STRPOS(appeal_reason, 'for') + 4)) as appeal_reason,
            outcome,
            outcome = 'Overturned' as is_overturned, 
            round(cast(overturn_amount as numeric),2) as overturn_amount,
            cast(days_to_resolution as int64) as days_to_resolve,
            submitted_by
        FROM {{source('rcm_raw', 'fact_appeals')}}       
    )

        SELECT * FROM src_appeals
       