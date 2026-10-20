import { listJabContracts } from '../services/api'
import { useApi } from './useApi'

export function useJabContracts() {
  return useApi((options) => listJabContracts(options))
}
