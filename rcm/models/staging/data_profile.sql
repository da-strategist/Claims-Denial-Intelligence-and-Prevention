
with profile_cte as 
    (SELECT * 
     FROM {{source ('rcm_raw', 'dim_patients')}} )


, cpt_codes as 
    (SELECT * 
    FROM {{source ('rcm_raw', 'dim_cpt_codes')}})

, billing_type as 
    (SELECT distinct billing_type
    FROM cpt_codes)

, departments as 
    (SELECT * 
    FROM {{source ('rcm_raw', 'dim_departments')}})

, facilities as 
    (SELECT *
    FROM {{source ('rcm_raw', 'dim_facilities')}})

, icd_codes as 
    (SELECT * 
    FROM {{source ('rcm_raw', 'dim_icd10_codes')}})

, patients as 
    (SELECT * 
    FROM {{source ('rcm_raw', 'dim_patients')}})

, patient_count as 
    (SELECT DISTINCT COUNT('patient_id') as pt_count
    FROM patients)

, payer_contract as 
    (SELECT * 
    FROM {{source ('rcm_raw', 'dim_payer_contracts')}})
SELECT * FROM profile_cte


/*
Profile dimension tables (row counts, null rates, cardinality)
- [x] 5.2 Profile fact tables (distributions, date ranges, key metrics)
- [x] 5.3 Identify and document the Self-Pay denial bug (self-pay patients should have 0 denials)
- [x] 5.4 Check referential integrity (foreign keys between fact and dim tables)
- [x] 5.5 Document data quality findings and decisions
*/

