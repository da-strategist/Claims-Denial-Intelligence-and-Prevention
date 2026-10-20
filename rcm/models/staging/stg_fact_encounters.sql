
WITH src_encounterss as 

    (
      SELECT  
        encounter_id,
        claim_id,
        encounter_type,
        cast(admit_date as date) as admit_date,
        cast(discharge_date as date) as discharge_date,
        length_of_stay,
        admit_source,
        discharge_disposition,
        severity_of_illness,
        risk_of_mortality,
        cast(drg_code as string)            as drg_code,
        round(cast(drg_weight as numeric), 4)   as drg_weight,
        round(cast(expected_los as numeric), 2)  as expected_los,
        is_readmission_30day
    FROM {{source('rcm_raw', 'fact_encounters')}}

    )
, cleaned_encounters AS (
    SELECT
        encounter_id,
        claim_id,
        encounter_type,
        admit_date,
        discharge_date,
        length_of_stay,
        admit_source,
        discharge_disposition,
        severity_of_illness,
        risk_of_mortality,
        drg_code,
        drg_weight,
        expected_los,
        round(length_of_stay - expected_los, 2)  as los_variance,
        is_readmission_30day,
        admit_date is not null       as is_inpatient
    FROM src_encounterss
    )
        SELECT * FROM src_encounterss