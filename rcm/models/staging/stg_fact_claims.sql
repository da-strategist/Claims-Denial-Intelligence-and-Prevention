

WITH fct_claims as 

    (SELECT 
        payer_id, 
        facility_id,
        department_id,
        service_date,
        submission_date,
        round(total_charge, 2) as total_charge,
        round(total_allowed, 2) as total_allowed,
        round(total_paid,2) as total_paid,
        round(patient_responsibility, 2) as amount_pt_charged,
        round((total_paid) + (patient_responsibility),2) as bill_confirmation,
        status,
        claim_type,
        place_of_service,
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
        payer_id, 
        facility_id,
        department_id,
        service_date,
        submission_date,
        total_charge,
        total_allowed,
        total_paid,
        amount_pt_charged,
        bill_confirmation,
        CASE WHEN total_allowed = bill_confirmation THEN 1 ELSE 0 END as bill_conf_status,
        status,
        claim_type,
        place_of_service,
        primary_icd10,
        days_in_ar,
        is_clean_claim,
        pa_required,
        pa_obtained,
        pa_number
    FROM fct_claims
    )
, non as 
    (
    SELECT * FROM cleaned 
    WHERE bill_conf_status = 0
    )
select * from cleaned