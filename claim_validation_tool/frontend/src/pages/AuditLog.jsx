import { useState } from 'react'
import { FIELD_CLASS } from '../constants'
import { useApi } from '../hooks/useApi'
import { listAuditEvents, verifyAuditLog } from '../services/api'

const OUTCOME_STYLES = {
  success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  denied: 'border-amber-200 bg-amber-50 text-amber-800',
  failed: 'border-red-200 bg-red-50 text-red-700',
}

const EMPTY_FILTERS = { username: '', record_id: '', outcome: '' }

function ChainStatus() {
  const { data, error } = useApi((options) => verifyAuditLog(options))
  if (error) return <p className="text-sm text-red-700">Could not verify the log — {error}</p>
  if (!data) return null
  return data.ok ? (
    <p role="status" className="text-sm text-emerald-700">
      ✓ Hash chain intact across {data.events.toLocaleString()} events: nothing has been edited
      or removed.
    </p>
  ) : (
    <p role="alert" className="text-sm font-semibold text-red-700">
      ✗ The log was altered at event {data.first_bad_seq}: events from there on can’t be trusted.
    </p>
  )
}

function Details({ event }) {
  const parts = [
    ...Object.entries(event.records).map(([key, value]) => `${key} ${value}`),
    ...Object.entries(event.query).map(([key, value]) => `${key}=${value}`),
    ...Object.entries(event.detail).map(([key, value]) => `${key}: ${value}`),
  ]
  return <span className="text-gray-600">{parts.join(' · ') || '—'}</span>
}

/** Who did what to which record, newest first (admins only). */
export default function AuditLog() {
  const [draft, setDraft] = useState(EMPTY_FILTERS)
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const { data: events, loading, error } = useApi(
    (options) => listAuditEvents({ ...filters, limit: 200 }, options),
    JSON.stringify(filters),
  )

  return (
    <div className="space-y-5 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Audit Log</h1>
        <p className="text-sm text-gray-500">
          Every API request: who made it, the records involved, and whether it was allowed
        </p>
      </div>
      <ChainStatus />

      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault()
          setFilters(draft)
        }}
      >
        <label className="space-y-1 text-xs font-medium text-gray-600">
          <span className="block">User</span>
          <input
            className={FIELD_CLASS}
            value={draft.username}
            onChange={(e) => setDraft({ ...draft, username: e.target.value })}
          />
        </label>
        <label className="space-y-1 text-xs font-medium text-gray-600">
          <span className="block">Record ID</span>
          <input
            className={FIELD_CLASS}
            placeholder="CLM0000001"
            value={draft.record_id}
            onChange={(e) => setDraft({ ...draft, record_id: e.target.value })}
          />
        </label>
        <label className="space-y-1 text-xs font-medium text-gray-600">
          <span className="block">Outcome</span>
          <select
            className={FIELD_CLASS}
            value={draft.outcome}
            onChange={(e) => setDraft({ ...draft, outcome: e.target.value })}
          >
            <option value="">Any</option>
            <option value="success">Success</option>
            <option value="denied">Denied</option>
            <option value="failed">Failed</option>
          </select>
        </label>
        <button
          type="submit"
          className="rounded-lg bg-gray-900 px-3 py-2 text-sm font-semibold text-white hover:bg-gray-700"
        >
          Filter
        </button>
      </form>

      {error && <p className="text-sm text-red-700">Could not load the audit log — {error}</p>}
      {loading && !events && <p className="text-sm text-gray-500">Loading events…</p>}
      {events && (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-3 py-2">When</th>
                <th className="px-3 py-2">User</th>
                <th className="px-3 py-2">Action</th>
                <th className="px-3 py-2">Records and details</th>
                <th className="px-3 py-2">Outcome</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {events.map((event) => (
                <tr key={event.seq} className="align-top">
                  <td className="whitespace-nowrap px-3 py-2 text-gray-600">
                    {new Date(event.at).toLocaleString()}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">
                    {event.username ?? <span className="text-gray-400">signed out</span>}
                    {event.role && <span className="block text-xs text-gray-400">{event.role}</span>}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-gray-800">{event.action}</td>
                  <td className="px-3 py-2 text-xs">
                    <Details event={event} />
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">
                    <span
                      className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${OUTCOME_STYLES[event.outcome]}`}
                    >
                      {event.status_code} {event.outcome}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {events.length === 0 && (
            <p className="p-4 text-sm text-gray-500">No events match these filters.</p>
          )}
        </div>
      )}
    </div>
  )
}
