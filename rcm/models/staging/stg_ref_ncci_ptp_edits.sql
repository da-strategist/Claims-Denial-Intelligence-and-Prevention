
WITH src_ref_nccpi as
    (
        SELECT 
            edit_id,
            cast(column_1_cpt as string)            as column_1_cpt,
            cast(column_2_cpt as string)            as column_2_cpt,
            cast(modifier_indicator as int64)       as modifier_indicator,
            modifier_indicator_desc,
            cast(effective_date as date)            as effective_date,
            termination_date,
            rationale,
            edit_type,
            source
        FROM {{source ('rcm_raw', 'ref_ncci_ptp_edits')}}
    )
        SELECT * FROM src_ref_nccpi
        WHERE termination_date IS NOT NULL