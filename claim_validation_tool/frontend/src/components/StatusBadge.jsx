import { VALIDATION_STATUSES } from '../constants'

const BADGE_BASE =
  'inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-semibold'

const CLAIM_STATUS_STYLES = {
  Paid: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  Denied: 'bg-red-50 text-red-800 border-red-200',
}

/** Payer adjudication outcome (Paid / Denied). */
export function ClaimStatusBadge({ status }) {
  return (
    <span
      className={`${BADGE_BASE} ${CLAIM_STATUS_STYLES[status] ?? 'border-gray-200 bg-gray-50 text-gray-700'}`}
    >
      {status}
    </span>
  )
}

/** Pre-submission validation result (Pass / Warning / Error / AI Fix). */
export function ValidationBadge({ status }) {
  const config = VALIDATION_STATUSES[status]
  if (!config) return <span className="text-sm text-gray-300">—</span>
  return (
    <span className={`${BADGE_BASE} ${config.style}`}>
      <span aria-hidden="true">{config.icon}</span>
      {config.label}
    </span>
  )
}

const SEVERITY_STYLES = {
  error: 'bg-red-50 text-red-700 border-red-200',
  warning: 'bg-amber-50 text-amber-700 border-amber-200',
  info: 'bg-sky-50 text-sky-700 border-sky-200',
}

export function SeverityBadge({ severity }) {
  return (
    <span className={`${BADGE_BASE} capitalize ${SEVERITY_STYLES[severity] ?? ''}`}>
      {severity}
    </span>
  )
}
