import { useId, useState } from 'react'
import { INPUT_CLASS } from '../constants'
import { useApi } from '../hooks/useApi'
import { createApiKey, listApiKeys, revokeApiKey } from '../services/api'

const day = (value) => new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })

/** The new key, once. It can't be shown again, so it stays until it's dismissed. */
function NewKey({ created, onDone }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(created.token)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }
  return (
    <div className="space-y-2 rounded-md border border-amber-200 bg-amber-50 p-4">
      <p className="text-sm font-medium text-gray-900">Copy the key for {created.key.name} now</p>
      <p className="text-sm text-gray-700">It won’t be shown again. Keep it in the system’s secret store, not in email or chat.</p>
      <code className="block break-all rounded bg-white p-2 font-mono text-xs text-gray-900">{created.token}</code>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn-secondary btn-sm" onClick={copy}>
          {copied ? 'Copied' : 'Copy key'}
        </button>
        <button type="button" className="btn-secondary btn-sm" onClick={onDone}>
          I’ve saved it
        </button>
      </div>
    </div>
  )
}

function KeyRow({ apiKey, onRevoked }) {
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const revoke = async () => {
    setBusy(true)
    setError(null)
    try {
      await revokeApiKey(apiKey.id)
      setConfirming(false)
      onRevoked()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }
  const revoked = Boolean(apiKey.revoked_at)
  return (
    <li className="py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0 text-sm">
          <p className={revoked ? 'font-medium text-gray-500' : 'font-medium text-gray-900'}>{apiKey.name}</p>
          <p className="text-xs text-gray-500">
            Shown in the audit log as <code className="font-mono">api.{apiKey.id}</code> · Added {day(apiKey.created_at)} by {apiKey.created_by} ·{' '}
            {revoked
              ? `Revoked ${day(apiKey.revoked_at)} by ${apiKey.revoked_by}`
              : apiKey.last_used_at
                ? `Last used ${day(apiKey.last_used_at)}`
                : 'Not used yet'}
          </p>
        </div>
        {!revoked &&
          (confirming ? (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-gray-700">The system using it stops working.</span>
              <button type="button" className="btn-secondary btn-sm" disabled={busy} onClick={revoke}>
                Yes, revoke
              </button>
              <button type="button" className="btn-secondary btn-sm" onClick={() => setConfirming(false)}>
                Keep it
              </button>
            </div>
          ) : (
            <button type="button" className="btn-secondary btn-sm" onClick={() => setConfirming(true)}>
              Revoke
            </button>
          ))}
      </div>
      {error && (
        <p role="alert" className="mt-1 text-sm text-red-700">
          Could not revoke the key — {error}
        </p>
      )}
    </li>
  )
}

/** Keys for the hospital's own systems to send claims and read back their errors and fixes. */
export default function ApiKeysCard() {
  const { data, error, reload } = useApi((options) => listApiKeys(options))
  const [name, setName] = useState('')
  const [created, setCreated] = useState(null)
  const [problem, setProblem] = useState(null)
  const [busy, setBusy] = useState(false)
  const nameId = useId()

  if (error) {
    return (
      <section className="card p-6">
        <p role="alert" className="text-sm text-red-700">
          Could not load the API keys — {error}
        </p>
      </section>
    )
  }
  if (!data) return null

  const add = async (event) => {
    event.preventDefault()
    setBusy(true)
    setProblem(null)
    try {
      setCreated(await createApiKey(name.trim()))
      setName('')
      reload()
    } catch (err) {
      setProblem(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-label="API keys" className="card space-y-4 p-6">
      <div>
        <h2 className="text-[15px] font-semibold text-gray-900">API keys</h2>
        <p className="text-sm text-gray-500">
          Let your billing or hospital system send claims here and get back errors and suggested fixes. A key can send
          and read claims across your whole organisation, and nothing else. Nothing it sends goes to a payer.
        </p>
      </div>
      {created && <NewKey created={created} onDone={() => setCreated(null)} />}
      {data.length > 0 && (
        <ul className="divide-y divide-gray-100">
          {data.map((apiKey) => (
            <KeyRow key={apiKey.id} apiKey={apiKey} onRevoked={reload} />
          ))}
        </ul>
      )}
      <form className="flex flex-wrap items-end gap-2" onSubmit={add}>
        <label htmlFor={nameId} className="min-w-[14rem] flex-1 space-y-1 text-sm font-medium text-gray-800">
          <span className="block">Which system is this key for?</span>
          <input
            id={nameId}
            className={INPUT_CLASS}
            maxLength={60}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <button type="submit" className="btn-primary" disabled={busy || !name.trim()}>
          Create key
        </button>
      </form>
      {problem && (
        <p role="alert" className="text-sm text-red-700">
          Could not create the key — {problem}
        </p>
      )}
    </section>
  )
}
