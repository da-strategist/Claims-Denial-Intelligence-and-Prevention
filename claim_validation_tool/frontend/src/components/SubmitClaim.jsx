import { useId, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { handOffClaim, reopenClaim, submitClaim } from '../services/api'
import HandoffExport from './HandoffExport'

const BLOCKING_SEVERITIES = new Set(['error', 'warning'])

/** Sending through VeriClaim: blocked, like the backend, while any rule error or warning remains. */
function SendRoute({ primary, blocked, disabled, busy, onSend }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <button
        type="button"
        onClick={onSend}
        disabled={blocked || disabled}
        className={primary ? 'btn-primary' : 'btn-secondary'}
      >
        {busy ? 'Submitting…' : 'Mark as submitted'}
      </button>
      <span className="text-sm text-gray-600">
        {blocked
          ? 'Resolve every error and warning before submitting.'
          : 'Sends from VeriClaim today and tracks it as pending.'}
      </span>
    </div>
  )
}

/** The billing system sends the claim. Open issues may be fixed there, once acknowledged. */
function HandOffRoute({ primary, askToConfirm, disabled, busy, onHandOff }) {
  const [acknowledged, setAcknowledged] = useState(false)
  const id = useId()
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => onHandOff(acknowledged)}
          disabled={disabled || (askToConfirm && !acknowledged)}
          className={primary ? 'btn-primary' : 'btn-secondary'}
        >
          {busy ? 'Handing off…' : 'Hand off to billing system'}
        </button>
        <span className="text-sm text-gray-600">You send it from your own system. Nothing goes to the payer from here.</span>
      </div>
      {askToConfirm && (
        <label htmlFor={id} className="flex items-start gap-2 text-sm text-gray-700">
          <input
            id={id}
            type="checkbox"
            className="mt-0.5"
            checked={acknowledged}
            onChange={(event) => setAcknowledged(event.target.checked)}
          />
          This claim still has open issues. We’ll resolve them in our billing system.
        </label>
      )}
    </div>
  )
}

/** A claim the billing system now holds. Reopening risks a duplicate, so it must be confirmed. */
function HandedOff({ claim, onChanged }) {
  const [reopening, setReopening] = useState(false)
  const [notSent, setNotSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const id = useId()
  const { handoff } = claim

  const reopen = async () => {
    setBusy(true)
    setError(null)
    try {
      onChanged(await reopenClaim(claim.claim_id))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-3 rounded-2xl bg-white p-4 ring-1 ring-gray-200/70">
      <p className="text-sm text-gray-700">
        Handed off to your billing system
        {handoff && ` on ${handoff.handed_off_on} by ${handoff.handed_off_by}`}. Send it from there.
      </p>
      {handoff?.open_issues.length > 0 && (
        <div className="text-sm text-amber-800">
          Open when it was handed off:
          <ul className="mt-1 list-disc pl-5">
            {handoff.open_issues.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        </div>
      )}
      <HandoffExport claimId={claim.claim_id} />
      {reopening ? (
        <div className="space-y-2">
          <p className="text-sm text-gray-600">Any file you already downloaded will be out of date, so don’t use it after reopening.</p>
          <label htmlFor={id} className="flex items-start gap-2 text-sm text-gray-700">
            <input
              id={id}
              type="checkbox"
              className="mt-0.5"
              checked={notSent}
              onChange={(event) => setNotSent(event.target.checked)}
            />
            Our billing system hasn’t sent this claim to the payer.
          </label>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-primary btn-sm" disabled={!notSent || busy} onClick={reopen}>
              {busy ? 'Reopening…' : 'Reopen as draft'}
            </button>
            <button type="button" className="btn-secondary btn-sm" onClick={() => setReopening(false)}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button type="button" className="btn-secondary btn-sm" onClick={() => setReopening(true)}>
          Reopen claim
        </button>
      )}
      {error && (
        <p role="alert" className="text-sm text-red-700">
          Could not reopen — {error}
        </p>
      )}
    </div>
  )
}

/**
 * How a Draft leaves: handed off to the hospital's billing system, or submitted from here.
 * Both are always offered; the organisation's default comes first. `onSubmitted` receives
 * { claim, validation } once the claim has moved on.
 */
export default function SubmitClaim({ claim, validation, onSubmitted }) {
  const auth = useAuth()
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const [refusedForIssues, setRefusedForIssues] = useState(false)

  if (claim.status === 'Handed off') return <HandedOff claim={claim} onChanged={onSubmitted} />
  if (claim.status !== 'Draft') return null

  const blocking = (validation?.findings ?? []).filter((f) => BLOCKING_SEVERITIES.has(f.severity))
  const blocked = blocking.length > 0 || ['error', 'aifix', 'warning'].includes(validation?.status)
  const sendFirst = auth?.user?.organisation?.default_claim_route === 'send'
  const disabled = Boolean(busy) || !validation

  const act = async (name, call) => {
    setBusy(name)
    setError(null)
    try {
      onSubmitted(await call())
    } catch (err) {
      // The final check runs with today's date, so it can find what the page hasn't shown yet
      if (name === 'hand-off' && err.status === 422) setRefusedForIssues(true)
      setError(err.message)
    } finally {
      setBusy(null)
    }
  }

  const send = (
    <SendRoute
      key="send"
      primary={sendFirst}
      blocked={blocked}
      disabled={disabled}
      busy={busy === 'send'}
      onSend={() => act('send', () => submitClaim(claim.claim_id))}
    />
  )
  const handOff = (
    <HandOffRoute
      key="hand-off"
      primary={!sendFirst}
      askToConfirm={blocked || refusedForIssues}
      disabled={disabled}
      busy={busy === 'hand-off'}
      onHandOff={(acknowledged) => act('hand-off', () => handOffClaim(claim.claim_id, acknowledged))}
    />
  )

  return (
    <div className="space-y-3 rounded-2xl bg-white p-4 ring-1 ring-gray-200/70">
      {sendFirst ? [send, handOff] : [handOff, send]}
      {error && (
        <p role="alert" className="text-sm text-red-700">
          Could not finish that — {error}
        </p>
      )}
    </div>
  )
}
