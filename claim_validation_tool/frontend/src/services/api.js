// Centralized API client — components and hooks never call fetch directly.

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'

function toQueryString(params = {}) {
  const entries = Object.entries(params).filter(
    ([, value]) => value !== undefined && value !== null && value !== '',
  )
  return entries.length ? `?${new URLSearchParams(entries)}` : ''
}

async function request(path, { params, signal } = {}) {
  const res = await fetch(`${API_BASE}${path}${toQueryString(params)}`, { signal })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = typeof body?.detail === 'string' ? body.detail : null
    throw new Error(detail ?? `Request failed: ${res.status} ${res.statusText}`)
  }
  return res.json()
}

export const getHealth = (options) => request('/health', options)

export const listClaims = (params, options) => request('/claims', { ...options, params })

export const getClaim = (claimId, options) =>
  request(`/claims/${encodeURIComponent(claimId)}`, options)

export const listPayers = (options) => request('/payers', options)
