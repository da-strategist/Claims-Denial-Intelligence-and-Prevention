import { useState } from 'react'
import { submitClaim } from '../services/api'

const BLOCKING_SEVERITIES = new Set(['error', 'warning'])

/**
 * "Mark as submitted" for a Draft claim. Like the backend, it's blocked while any rule
 * error or warning remains. `onSubmitted` receives { claim, validation } for the
 * now-Pending claim.
 */
export default function SubmitClaim({ claim, validation, onSubmitted }) {
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  if (claim.status !== 'Draft') return null

  const blocking = (validation?.findings ?? []).filter((f) => BLOCKING_SEVERITIES.has(f.severity))
  const blocked = blocking.length > 0 || ['error', 'aifix', 'warning'].includes(validation?.status)

  const submit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      onSubmitted(await submitClaim(claim.claim_id))
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-1.5 rounded-2xl bg-white p-4 ring-1 ring-gray-200/70">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={submit}
          disabled={blocked || submitting || !validation}
          className="btn-primary"
        >
          {submitting ? 'Submitting…' : 'Mark as submitted'}
        </button>
        <span className="text-sm text-gray-600">
          {blocked
            ? 'Resolve every error and warning before submitting.'
            : 'Draft — sends today and starts tracking it as pending.'}
        </span>
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-700">
          Could not submit — {error}
        </p>
      )}
    </div>
  )
}
