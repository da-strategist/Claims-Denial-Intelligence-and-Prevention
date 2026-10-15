// Centralized API client — components and hooks never call fetch directly.

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'

function toQueryString(params = {}) {
  const entries = Object.entries(params).filter(
    ([, value]) => value !== undefined && value !== null && value !== '',
  )
  return entries.length ? `?${new URLSearchParams(entries)}` : ''
}

async function request(path, { params, body, method = 'GET', signal } = {}) {
  const init = { method, signal }
  if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' }
    init.body = JSON.stringify(body)
  }
  const res = await fetch(`${API_BASE}${path}${toQueryString(params)}`, init)
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    const detail = typeof data?.detail === 'string' ? data.detail : null
    throw new Error(detail ?? `Request failed: ${res.status} ${res.statusText}`)
  }
  return res.status === 204 ? null : res.json()
}

export const getHealth = (options) => request('/health', options)

export const listClaims = (params, options) => request('/claims', { ...options, params })

export const getClaim = (claimId, options) =>
  request(`/claims/${encodeURIComponent(claimId)}`, options)

export const listPayers = (options) => request('/payers', options)

/** Validate up to 200 claims against the enabled rules. Results keep the order of `claimIds`. */
export const validateClaims = (claimIds, options) =>
  request('/validate', { ...options, method: 'POST', body: { claim_ids: claimIds } })
