
WITH src_dim_payer_contracts AS (
    SELECT
        contract_id,
        payer_id,
        cpt_category,
        round(cast(reimbursement_pct_of_charge as numeric), 4)  as reimbursement_pct_of_charge,
        cast(effective_date as date)                            as effective_date,
        cast(end_date as date)                                  as end_date,
        status
    FROM {{ source('rcm_raw', 'dim_payer_contracts') }}
)

, cleaned_payer_contracts AS (
    SELECT
        contract_id,
        payer_id,
        cpt_category,
        reimbursement_pct_of_charge,
        effective_date,
        end_date,
        status,
        status = 'Active'                                       as is_active
    FROM src_dim_payer_contracts
)

SELECT * FROM cleaned_payer_contracts
