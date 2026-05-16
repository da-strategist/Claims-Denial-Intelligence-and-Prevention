

WITH fct_claims as 

    (SELECT 
        claim_id,
        patient_id,
        provider_id,
        payer_id, 
        facility_id,
        department_id,
        cast(service_date as date) as service_date,
        cast(submission_date as date) as submission_date,
        round(total_charge, 2) as total_charge,
        round(total_allowed, 2) as total_allowed,
        round(total_paid,2) as total_paid,
        round(patient_responsibility, 2) as amount_pt_charged,
        round((total_paid) + (patient_responsibility),2) as total_collected,
        status,
        claim_type,
        cast(place_of_service as string) service_point,
        primary_icd10,
        days_in_ar,
        is_clean_claim,
        pa_required,
        pa_obtained,
        pa_number
    FROM {{source ('rcm_raw', 'fact_claims')}})

, cleaned as 
    (
    SELECT 
        claim_id,
        patient_id,
        provider_id,
        payer_id, 
        facility_id,
        department_id,
        service_date,
        submission_date,
        total_charge,
        total_allowed,
        total_paid,
        amount_pt_charged,
        total_collected,
        CASE WHEN total_allowed = total_collected THEN 1 ELSE 0 END as bill_match_status,
        status,
        claim_type,
        service_point,
        primary_icd10,
        days_in_ar,
        is_clean_claim,
        pa_required,
        pa_obtained,
        pa_number,
        date_diff(submission_date, service_date, day) as service_to_submission_days
    FROM fct_claims
    )
select * from cleaned