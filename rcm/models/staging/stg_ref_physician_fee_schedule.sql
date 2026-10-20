
WITH src_ref_physician_fee_schedule AS (
    SELECT
        cast(cpt_code as string)                                        as cpt_code,
        description,
        category,
        round(cast(work_rvu as numeric), 4)                            as work_rvu,
        round(cast(pe_rvu_facility as numeric), 4)                     as pe_rvu_facility,
        round(cast(pe_rvu_nonfacility as numeric), 4)                  as pe_rvu_nonfacility,
        round(cast(mp_rvu as numeric), 4)                              as mp_rvu,
        round(cast(total_rvu_facility as numeric), 4)                  as total_rvu_facility,
        round(cast(total_rvu_nonfacility as numeric), 4)               as total_rvu_nonfacility,
        round(cast(conversion_factor_2024 as numeric), 4)              as conversion_factor_2024,
        round(cast(conversion_factor_2025 as numeric), 4)              as conversion_factor_2025,
        round(cast(medicare_payment_facility_2024 as numeric), 2)      as medicare_payment_facility_2024,
        round(cast(medicare_payment_nonfacility_2024 as numeric), 2)   as medicare_payment_nonfacility_2024,
        round(cast(medicare_payment_facility_2025 as numeric), 2)      as medicare_payment_facility_2025,
        round(cast(medicare_payment_nonfacility_2025 as numeric), 2)   as medicare_payment_nonfacility_2025,
        round(cast(gpci_work as numeric), 4)                           as gpci_work,
        round(cast(gpci_pe as numeric), 4)                             as gpci_pe,
        round(cast(gpci_mp as numeric), 4)                             as gpci_mp,
        locality,
        mac,
        status_indicator
    FROM {{ source('rcm_raw', 'ref_physician_fee_schedule') }}
)

, cleaned_physician_fee_schedule AS (
    SELECT
        cpt_code,
        description,
        category,
        work_rvu,
        pe_rvu_facility,
        pe_rvu_nonfacility,
        mp_rvu,
        total_rvu_facility,
        total_rvu_nonfacility,
        conversion_factor_2024,
        conversion_factor_2025,
        medicare_payment_facility_2024,
        medicare_payment_nonfacility_2024,
        medicare_payment_facility_2025,
        medicare_payment_nonfacility_2025,
        round(medicare_payment_facility_2025 - medicare_payment_facility_2024, 2)           as yoy_payment_change_facility,
        round(medicare_payment_nonfacility_2025 - medicare_payment_nonfacility_2024, 2)     as yoy_payment_change_nonfacility,
        gpci_work,
        gpci_pe,
        gpci_mp,
        locality,
        mac,
        status_indicator
    FROM src_ref_physician_fee_schedule
)

SELECT * FROM cleaned_physician_fee_schedule
