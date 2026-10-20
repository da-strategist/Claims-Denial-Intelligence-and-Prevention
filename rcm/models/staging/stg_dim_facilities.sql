
WITH src_dim_facilities AS (
    SELECT
        facility_id,
        facility_name,
        facility_type,
        cast(bed_count as int64)    as bed_count,
        address,
        status,
        cast(tax_id as string)      as tax_id
    FROM {{ source('rcm_raw', 'dim_facilities') }}
)

, cleaned_facilities AS (
    SELECT
        facility_id,
        facility_name,
        facility_type,
        bed_count,
        address,
        status,
        status = 'Active'           as is_active,
        tax_id
    FROM src_dim_facilities
)

SELECT * FROM cleaned_facilities
