import { useState } from 'react'
import { submitClaim } from '../services/api'

const BLOCKING = new Set(['error', 'aifix'])

/**
 * "Mark as submitted" for a Draft claim. Blocked while rule errors remain, matching the
 * backend. `onSubmitted` receives { claim, validation } for the now-Pending claim.
 */
export default function SubmitClaim({ claim, validation, onSubmitted }) {
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  if (claim.status !== 'Draft') return null

  const blocked = BLOCKING.has(validation?.status)

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
    <div className="space-y-1.5 rounded-lg border border-dashed border-gray-300 bg-white p-3">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={submit}
          disabled={blocked || submitting || !validation}
          className="rounded-lg bg-gray-900 px-3 py-1.5 text-sm font-semibold text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {submitting ? 'Submitting…' : 'Mark as submitted'}
        </button>
        <span className="text-sm text-gray-600">
          {blocked
            ? 'Resolve the rule errors before submitting.'
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
