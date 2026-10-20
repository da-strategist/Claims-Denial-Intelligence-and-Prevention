import { useMemo } from 'react'
import { listDepartments, listRuleFields, listRules } from '../services/api'
import { useApi } from './useApi'

export function useRules() {
  return useApi((options) => listRules(options))
}

/** Rule fields keyed by field name. */
export function useRuleFields() {
  const { data } = useApi((options) => listRuleFields(options))
  return useMemo(() => Object.fromEntries((data ?? []).map((f) => [f.field, f])), [data])
}

/** Departments keyed by department_id. */
export function useDepartmentLookup() {
  const { data } = useApi((options) => listDepartments(options))
  return useMemo(
    () => Object.fromEntries((data ?? []).map((d) => [d.department_id, d])),
    [data],
  )
}
