// Centralized API client — components and hooks never call fetch directly.

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'

function toQueryString(params = {}) {
  const entries = Object.entries(params).filter(
    ([, value]) => value !== undefined && value !== null && value !== '',
  )
  return entries.length ? `?${new URLSearchParams(entries)}` : ''
}

/**
 * FastAPI returns a string `detail` for HTTP errors and a list of
 * { loc, msg } for request validation (422) errors. Turn either into one message.
 */
function errorMessage(detail) {
  if (typeof detail === 'string') return detail
  if (!Array.isArray(detail)) return null
  return detail
    .map(({ loc = [], msg = '' }) => {
      const where = loc.filter((part) => part !== 'body').join(' › ')
      const text = msg.replace(/^Value error, /, '')
      return where ? `${where}: ${text}` : text
    })
    .join('; ')
}

// The dev proxy answers 502-504 when the API isn't running; fetch itself rejects with a TypeError
const UNREACHABLE = 'Can’t reach the API server. Check that the backend is running.'
const GATEWAY_ERRORS = new Set([502, 503, 504])

async function request(path, { params, body, method = 'GET', signal } = {}) {
  const init = { method, signal }
  if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' }
    init.body = JSON.stringify(body)
  }
  let res
  try {
    res = await fetch(`${API_BASE}${path}${toQueryString(params)}`, init)
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new Error(UNREACHABLE, { cause: err })
  }
  if (GATEWAY_ERRORS.has(res.status)) throw new Error(UNREACHABLE)
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    throw new Error(
      errorMessage(data?.detail) ?? `Request failed: ${res.status} ${res.statusText}`,
    )
  }
  return res.status === 204 ? null : res.json()
}

export const getHealth = (options) => request('/health', options)

export const listClaims = (params, options) => request('/claims', { ...options, params })

export const getClaim = (claimId, options) =>
  request(`/claims/${encodeURIComponent(claimId)}`, options)

/** Enter a claim by hand. Returns { claim, validation }. */
export const createClaim = (claim) => request('/claims', { method: 'POST', body: claim })

/** Mark a Draft as submitted today (it becomes Pending). Refused while rule errors remain. */
export const submitClaim = (claimId) =>
  request(`/claims/${encodeURIComponent(claimId)}/submit`, { method: 'POST' })

export const listPayers = (options) => request('/payers', options)

/** Validate up to 200 claims against the enabled rules. Results keep the order of `claimIds`. */
export const validateClaims = (claimIds, options) =>
  request('/validate', { ...options, method: 'POST', body: { claim_ids: claimIds } })

export const listDepartments = (options) => request('/departments', options)

// --- Claim entry: registered patients and reference lists -------------------------

/** Registered patients by ID prefix or name words, with claim and denial counts. */
export const searchPatients = (params, options) => request('/patients', { ...options, params })

export const listProviders = (options) => request('/providers', options)

export const listFacilities = (options) => request('/facilities', options)

/** CPT codes with standard charges. */
export const listProcedureCodes = (options) => request('/codes/procedures', options)

/** Common ICD-10 codes, for suggestions. */
export const listDiagnosisCodes = (options) => request('/codes/diagnoses', options)

// --- Validation rules ---------------------------------------------------------

export const listRules = (options) => request('/rules', options)

/** Claim fields rule conditions can test, with type, allowed values, and valid operators. */
export const listRuleFields = (options) => request('/rules/fields', options)

export const createRule = (rule) => request('/rules', { method: 'POST', body: rule })

export const replaceRule = (ruleId, rule) =>
  request(`/rules/${encodeURIComponent(ruleId)}`, { method: 'PUT', body: rule })

export const updateRule = (ruleId, changes) =>
  request(`/rules/${encodeURIComponent(ruleId)}`, { method: 'PATCH', body: changes })

export const deleteRule = (ruleId) =>
  request(`/rules/${encodeURIComponent(ruleId)}`, { method: 'DELETE' })

/** Count the claims a draft rule ({ scope, conditions, condition_logic }) would flag. */
export const testRule = (definition, options) =>
  request('/rules/test', { ...options, method: 'POST', body: definition })

// --- AI Fix ------------------------------------------------------------------------

/** Validation, fix suggestions (with citations), and applied corrections for a claim. */
export const getClaimFixes = (claimId, options) =>
  request(`/aifix/${encodeURIComponent(claimId)}`, options)

/** Apply a suggestion; `values` supplies or overrides field values. Re-validates the claim. */
export const applyFix = (claimId, suggestionId, values = {}) =>
  request(`/aifix/${encodeURIComponent(claimId)}/apply`, {
    method: 'POST',
    body: { suggestion_id: suggestionId, values },
  })

/** Undo every correction on a claim, restoring its source values. */
export const undoCorrections = (claimId) =>
  request(`/aifix/${encodeURIComponent(claimId)}/corrections`, { method: 'DELETE' })

// --- Executive dashboard ---------------------------------------------------------

/** KPIs and chart data. Params: months (trailing, omit for all time), payer_id, department_id. */
export const getDashboard = (params, options) => request('/dashboard', { ...options, params })

// --- JAB Audit (conceptual) ------------------------------------------------------

/** Proposed ClaustraRCM <-> JAB Audit API contracts, with field tables, schemas, and examples. */
export const listJabContracts = (options) => request('/jab/contracts', options)

/** Ask the clarification assistant. Returns { answer, sources, mode, notice, claim_facts }. */
export const askAssistant = ({ question, claimId, topic }) =>
  request('/assistant', {
    method: 'POST',
    body: { question, claim_id: claimId ?? null, topic: topic ?? null },
  })
