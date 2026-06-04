
WITH src_dim_patients AS (
    SELECT
        patient_id,
        first_name,
        last_name,
        cast(age as int64)                          as age,
        gender,
        primary_payer_id,
        round(cast(risk_score as numeric), 4)       as risk_score,
        cast(zip_code as string)                    as zip_code,
        language,
        status
    FROM {{ source('rcm_raw', 'dim_patients') }}
)

, cleaned_patients AS (
    SELECT
        patient_id,
        first_name,
        last_name,
        age,
        gender,
        primary_payer_id,
        risk_score,
        zip_code,
        language,
        status,
        status = 'Active'                           as is_active
    FROM src_dim_patients
)

SELECT * FROM cleaned_patients
