
WITH src_scheduling AS (
    SELECT
        appointment_id,
        claim_id,
        cast(scheduled_date as date)            as scheduled_date,
        cast(appointment_date as date)          as appointment_date,
        appointment_type,
        cast(scheduling_lead_days as int64)     as scheduling_lead_days,
        appointment_status,
        cast(prior_no_show_count as int64)      as prior_no_show_count,
        cast(check_in_minutes_early as int64)   as check_in_minutes_early,
        insurance_verified_at_scheduling,
        referral_required,
        referral_on_file,
        cast(appointment_duration_minutes as int64) as appointment_duration_minutes
    FROM {{ source('rcm_raw', 'fact_scheduling') }}
)

, cleaned_scheduling AS (
    SELECT
        appointment_id,
        claim_id,
        scheduled_date,
        appointment_date,
        appointment_type,
        scheduling_lead_days,
        appointment_status,
        appointment_status = 'no-show'              as is_no_show,
        prior_no_show_count,
        check_in_minutes_early,
        insurance_verified_at_scheduling,
        referral_required,
        referral_on_file,
        (referral_required = true and referral_on_file = false) as referral_gap,
        appointment_duration_minutes
    FROM src_scheduling
)

SELECT * FROM cleaned_scheduling
