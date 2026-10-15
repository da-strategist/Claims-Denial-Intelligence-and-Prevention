import { useMemo } from 'react'
import { listClaims, listPayers } from '../services/api'
import { useApi } from './useApi'

export function useClaims(params) {
  return useApi((options) => listClaims(params, options), JSON.stringify(params))
}

/** Payers keyed by payer_id, for resolving names in tables. */
export function usePayerLookup() {
  const { data } = useApi((options) => listPayers(options))
  return useMemo(
    () => Object.fromEntries((data ?? []).map((payer) => [payer.payer_id, payer])),
    [data],
  )
}
