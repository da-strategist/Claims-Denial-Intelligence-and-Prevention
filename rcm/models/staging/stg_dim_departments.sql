
WITH src_dim_departments AS (
    SELECT
        department_id,
        department_name,
        service_line,
        round(cast(claim_share as numeric), 4)      as claim_share,
        round(cast(pa_frequency as numeric), 4)     as pa_frequency,
        cast(avg_daily_volume as int64)             as avg_daily_volume
    FROM {{ source('rcm_raw', 'dim_departments') }}
)

SELECT * FROM src_dim_departments
