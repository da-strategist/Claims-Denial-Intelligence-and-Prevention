
WITH src_ref_nppes_providers AS (
    SELECT
        provider_id,
        cast(npi as string)                                         as npi,
        entity_type,
        taxonomy_code,
        taxonomy_description,
        license_state,
        cast(license_number as string)                             as license_number,
        cast(enumeration_date as date)                             as enumeration_date,
        cast(last_update as date)                                  as last_update,
        npi_status,
        sole_proprietor,
        organization_name,
        organization_npi,
        enrolled_payers,
        medicare_enrolled,
        medicaid_enrolled,
        pecos_enrollment_date,
        opt_out_status
    FROM {{ source('rcm_raw', 'ref_nppes_providers') }}
)

SELECT * FROM src_ref_nppes_providers
