
WITH fct_claims as 

    (SELECT *
    FROM {{source ('rcm_raw', 'fact_claims')}})

, denials as 
    (SELECT *
    FROM {{source ('rcm_raw', 'fact_denials')}})

, appeals as
    (SELECT *
    FROM {{source ('rcm_raw', 'fact_appeals')}})

, claim_lines as
    (SELECT *
    FROM {{source ('rcm_raw', 'fact_claim_lines')}})

, remittance as
    (SELECT *
    FROM {{source ('rcm_raw', 'fact_remittance')}})

, encounters as
    (SELECT *
    FROM {{source ('rcm_raw', 'fact_encounters')}})

, workflow_events as
    (SELECT *
    FROM {{source ('rcm_raw', 'fact_workflow_events')}})

, claim_status_history as
    (SELECT *
    FROM {{source ('rcm_raw', 'fact_claim_status_history')}})

, charge_lag as
    (SELECT *
    FROM {{source ('rcm_raw', 'fact_charge_lag')}})

, scheduling as
    (SELECT *
    FROM {{source ('rcm_raw', 'fact_scheduling')}})

SELECT * FROM fct_claims