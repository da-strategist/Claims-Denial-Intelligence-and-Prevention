
WITH src AS (
    SELECT
        status_id,
        claim_id,
        cast(status_date as date)   as status_date,
        status_code,
        status_description,
        status_category,
        clearinghouse_status,
        days_since_submission
    FROM {{ source('rcm_raw', 'fact_claim_status_history') }}
)

SELECT * FROM src
