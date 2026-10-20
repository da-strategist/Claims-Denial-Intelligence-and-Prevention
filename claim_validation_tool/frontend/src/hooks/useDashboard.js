import { getDashboard } from '../services/api'
import { useApi } from './useApi'

export function useDashboard(params) {
  return useApi((options) => getDashboard(params, options), JSON.stringify(params))
}
