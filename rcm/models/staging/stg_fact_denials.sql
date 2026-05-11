
WITH fact_denials as 
    (
        SELECT *
        FROM {{source ('rcm_raw', 'fact_denials')}}
    )
SELECT * FROM fact_denials