
WITH src_charge_lag AS

    (
        SELECT 
            claim_id,
            cast(service_date as date) as service_date,
            cast(charge_entry_date as date) as charge_entry_date,
            cast(submission_date as date) as submission_date,
            cast(charge_lag_days as INT) as charge_lag_days,
            cast(submission_lag_days as INT) as submission_lag_days,
            cast(total_lag_days as INT) as total_lag_days,
            charge_lag_bucket,
            is_at_risk,
            is_critical_lag,
            entered_by_role
        FROM {{source('rcm_raw', 'fact_charge_lag')}}  
    )
, cleaned_charge_lag as
    (
        SELECT 
            claim_id,
            service_date,
            charge_entry_date,
            submission_date,
            charge_lag_days,
            submission_lag_days,
            total_lag_days,
            CASE WHEN (charge_lag_days) + (submission_lag_days) = total_lag_days THEN 1 else 0 end as lag_days_confirmation,
            charge_lag_bucket,
            is_at_risk,
            is_critical_lag,
            entered_by_role
        FROM src_charge_lag
    )
        SELECT * FROM src_charge_lag