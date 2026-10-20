import { useEffect, useMemo, useState } from 'react'
import { getClaim, getClaimFixes, listClaims, listPayers, validateClaims } from '../services/api'
import { useApi } from './useApi'

export function useClaims(params) {
  return useApi((options) => listClaims(params, options), JSON.stringify(params))
}

/** Claim with lines, denials, payer, and provider. Pass null to skip fetching. */
export function useClaimDetail(claimId) {
  return useApi(
    (options) => (claimId ? getClaim(claimId, options) : Promise.resolve(null)),
    claimId ?? '',
  )
}

/** AI Fix suggestions and corrections for a claim. */
export function useClaimFixes(claimId) {
  return useApi((options) => getClaimFixes(claimId, options), claimId)
}

/** Validation results for the given claims, keyed by claim_id. */
export function useClaimValidations(claimIds) {
  const key = claimIds.join(',')
  const state = useApi(
    (options) => (claimIds.length ? validateClaims(claimIds, options) : Promise.resolve([])),
    key,
  )
  const byId = useMemo(
    () => Object.fromEntries((state.data ?? []).map((result) => [result.claim_id, result])),
    [state.data],
  )
  return { ...state, byId }
}

/** Payers keyed by payer_id, for resolving names in tables. */
export function usePayerLookup() {
  const { data } = useApi((options) => listPayers(options))
  return useMemo(
    () => Object.fromEntries((data ?? []).map((payer) => [payer.payer_id, payer])),
    [data],
  )
}

/** `value`, updated only after it stops changing for `delayMs` (for search-as-you-type). */
export function useDebouncedValue(value, delayMs = 300) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}
