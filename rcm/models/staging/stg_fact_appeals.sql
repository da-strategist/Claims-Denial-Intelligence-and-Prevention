
WITH src_appeals as 

    (
        SELECT * 
        FROM {{source ('rcm_raw', 'fact_appeals')}}
    )

        SELECT * FROM src_appeals