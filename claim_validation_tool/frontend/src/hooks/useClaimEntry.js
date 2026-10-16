import { useMemo } from 'react'
import {
  listDiagnosisCodes,
  listFacilities,
  listProcedureCodes,
  listProviders,
  searchPatients,
} from '../services/api'
import { useApi } from './useApi'

/** Registered patients matching `search` (pass a debounced value). */
export function usePatientSearch(search) {
  return useApi(
    (options) =>
      search ? searchPatients({ search, page_size: 8 }, options) : Promise.resolve(null),
    search,
  )
}

const byKey = (data, key) => Object.fromEntries((data ?? []).map((row) => [row[key], row]))

/** Providers, facilities, and code sets for the claim form, each keyed by ID/code. */
export function useClaimEntryLists() {
  const providers = useApi((options) => listProviders(options))
  const facilities = useApi((options) => listFacilities(options))
  const procedures = useApi((options) => listProcedureCodes(options))
  const diagnoses = useApi((options) => listDiagnosisCodes(options))
  const lists = useMemo(
    () => ({
      providers: byKey(providers.data, 'provider_id'),
      facilities: byKey(facilities.data, 'facility_id'),
      procedures: byKey(procedures.data, 'cpt_code'),
      diagnoses: byKey(diagnoses.data, 'icd10_code'),
    }),
    [providers.data, facilities.data, procedures.data, diagnoses.data],
  )
  const error = providers.error ?? facilities.error ?? procedures.error ?? diagnoses.error
  return { ...lists, error }
}
