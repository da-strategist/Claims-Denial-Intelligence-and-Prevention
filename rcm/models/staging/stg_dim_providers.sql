
WITH src_dim_providers AS (
    SELECT
        provider_id,
        provider_name,
        cast(npi as string)                                             as npi,
        specialty,
        department_id,
        round(cast(coding_accuracy_score as numeric), 4)               as coding_accuracy_score,
        round(cast(documentation_completeness_score as numeric), 4)    as documentation_completeness_score,
        cast(years_experience as int64)                                as years_experience,
        status,
        credential
    FROM {{ source('rcm_raw', 'dim_providers') }}
)

SELECT * FROM src_dim_providers
