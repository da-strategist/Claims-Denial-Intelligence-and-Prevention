
WITH src_workflow_events AS (
    SELECT
        event_id,
        claim_id,
        workflow_step,
        cast(step_order as int64)               as step_order,
        cast(event_timestamp as timestamp)      as event_timestamp,
        status,
        issues_flagged,
        performed_by,
        cast(duration_minutes as int64)         as duration_minutes
    FROM {{ source('rcm_raw', 'fact_workflow_events') }}
)

, cleaned_workflow_events AS (
    SELECT
        event_id,
        claim_id,
        workflow_step,
        step_order,
        event_timestamp,
        cast(date(event_timestamp) as date)     as event_date,
        status,
        status = 'failed'                       as is_failed,
        issues_flagged,
        issues_flagged is not null              as has_issue,
        performed_by,
        duration_minutes
    FROM src_workflow_events
)

SELECT * FROM cleaned_workflow_events
