import { useState } from 'react'
import PageHeader, { Notice, Page } from '../components/PageHeader'
import { FIELD_CLASS } from '../constants'
import { useApi } from '../hooks/useApi'
import EmergencyAccessList from '../components/EmergencyAccessList'
import { endOrgEmergencyAccess, listAuditEvents, listOrgEmergencyAccess, verifyAuditLog } from '../services/api'

// Success is the norm, so it stays quiet
const OUTCOME_STYLES = {
  success: 'bg-gray-100 text-gray-600',
  denied: 'bg-amber-50 text-amber-800',
  failed: 'bg-red-50 text-red-700',
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
/** The platform's emergency access to this organisation: shown first when any is active. */
function EmergencySection() {
  const { data: grants, reload } = useApi((options) => listOrgEmergencyAccess(options))
  if (!grants?.length) return null
  return (
    <section aria-labelledby="org-emergency" className="card space-y-1 px-6 py-4">
      <h2 id="org-emergency" className="text-[15px] font-semibold text-gray-900">
        Platform emergency access
      </h2>
      <p className="text-xs text-gray-500">
        The service’s operators looking at your data, read-only, with their reason. You can end it at any time.
      </p>
      <EmergencyAccessList
        grants={grants}
        showOrganisation={false}
        onEnd={async (grant) => {
          await endOrgEmergencyAccess(grant.id)
          reload()
        }}
      />
    </section>
  )
}

export default function AuditLog() {
  const [draft, setDraft] = useState(EMPTY_FILTERS)
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const { data: events, loading, error } = useApi(
    (options) => listAuditEvents({ ...filters, limit: 200 }, options),
    JSON.stringify(filters),
  )

  return (
    <Page wide>
      <PageHeader
        title="Audit log"
        subtitle="Every request: who made it, the records involved, and whether it was allowed."
      />
      <ChainStatus />
      <EmergencySection />

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
          className="btn-primary"
        >
          Filter
        </button>
      </form>

      {error && <Notice>Could not load the audit log — {error}</Notice>}
      {loading && !events && <p className="text-sm text-gray-500">Loading events…</p>}
      {events && (
        <div className="card overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-gray-100 text-xs text-gray-500">
              <tr>
                <th className="px-4 py-3 font-medium">When</th>
                <th className="px-4 py-3 font-medium">User</th>
                <th className="px-4 py-3 font-medium">Action</th>
                <th className="px-4 py-3 font-medium">Records and details</th>
                <th className="px-4 py-3 font-medium">Outcome</th>
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
                  <td className="px-4 py-3 font-mono text-xs text-gray-800">{event.action}</td>
                  <td className="px-4 py-3 text-xs">
                    <Details event={event} />
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${OUTCOME_STYLES[event.outcome]}`}
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
    </Page>
  )
}
