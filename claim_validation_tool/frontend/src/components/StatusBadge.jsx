import { VALIDATION_STATUSES } from '../constants'

const PILL = 'inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium'

// Paid is green, a denial red; Draft and Pending are just where the claim is
const CLAIM_STATUS_STYLES = {
  Draft: 'border border-dashed border-gray-300 text-gray-600',
  Pending: 'bg-accent-soft text-accent',
  Paid: 'bg-emerald-50 text-emerald-700',
  Denied: 'bg-red-50 text-red-700',
}

/** Where the claim is with the payer: Draft → Pending → Paid / Denied. */
export function ClaimStatusBadge({ status, overdue = false }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className={`${PILL} ${CLAIM_STATUS_STYLES[status] ?? 'bg-gray-100 text-gray-600'}`}>
        {status}
      </span>
      {overdue && (
        <span
          className={`${PILL} bg-amber-50 text-amber-700`}
          title="Pending longer than this payer's average days to pay"
        >
          Overdue
        </span>
      )}
    </span>
  )
}

/** Pre-submission validation result (Pass / Warning / Error / AI Fix): a dot and a word. */
export function ValidationBadge({ status }) {
  const config = VALIDATION_STATUSES[status]
  if (!config) return <span className="text-sm text-gray-300">—</span>
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap text-xs font-medium ${config.text}`}>
      <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${config.dot}`} />
      {config.label}
    </span>
  )
}

const SEVERITY_STYLES = {
  error: 'bg-red-50 text-red-700',
  warning: 'bg-amber-50 text-amber-700',
  info: 'bg-gray-100 text-gray-600',
}

export function SeverityBadge({ severity }) {
  return <span className={`${PILL} capitalize ${SEVERITY_STYLES[severity] ?? ''}`}>{severity}</span>
}
