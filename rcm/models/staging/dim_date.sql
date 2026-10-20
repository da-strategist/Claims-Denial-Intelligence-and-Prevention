{{ config(materialized='table', schema='staging') }}

-- Grain: one row per calendar month
-- Primary key: date_key (MMYYYY e.g. '012026')

WITH date_spine AS (
    {{ dbt_utils.date_spine(
        datepart   = "month",
        start_date = "cast('2018-01-01' as date)",
        end_date   = "cast('2030-12-31' as date)"
    ) }}
)

SELECT
    format_date('%m%Y', date_month)       AS date_key,
    extract(month from date_month)        AS month_num,
    format_date('%B', date_month)         AS month_name,
    format_date('%b', date_month)         AS month_name_short,
    extract(year from date_month)         AS year_num,
    format_date('%Y-%m', date_month)      AS year_month

FROM date_spine