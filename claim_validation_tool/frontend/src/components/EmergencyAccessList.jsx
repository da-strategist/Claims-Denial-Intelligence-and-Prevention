// The platform's emergency (break-glass) access, for the Platform page and Audit Log
import { useState } from 'react'

const when = (iso) =>
  new Date(iso).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })

function grantState(grant, now) {
  if (grant.ended_at) return `Ended ${when(grant.ended_at)} by ${grant.ended_by}`
  if (new Date(grant.expires_at) <= now) return `Expired ${when(grant.expires_at)}`
  return `Active until ${when(grant.expires_at)}`
}

/** Emergency access grants, for the platform (all) or an organisation's admins (theirs). */
export default function EmergencyAccessList({ grants, orgNames = {}, onEnd, showOrganisation = true }) {
  // Shown in whole minutes, so the time the list was drawn is close enough
  const [now] = useState(() => new Date())
  if (!grants?.length) return <p className="py-3 text-sm text-gray-500">None.</p>
  return (
    <ul className="divide-y divide-gray-100">
      {grants.map((grant) => {
        const active = !grant.ended_at && new Date(grant.expires_at) > now
        return (
          <li key={grant.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
            <div className="min-w-0 flex-1 text-sm">
              <div className="font-medium text-gray-900">
                {grant.username}
                {showOrganisation && ` → ${orgNames[grant.organisation_id] ?? grant.organisation_id}`}
                <span className={`ml-2 text-xs font-normal ${active ? 'text-red-700' : 'text-gray-500'}`}>
                  {grantState(grant, now)}
                </span>
              </div>
              <div className="text-gray-600">“{grant.reason}”</div>
              <div className="text-xs text-gray-400">Started {when(grant.granted_at)} · {grant.id}</div>
            </div>
            {active && onEnd && (
              <button type="button" className="btn-danger btn-sm" onClick={() => onEnd(grant)}>
                End now
              </button>
            )}
          </li>
        )
      })}
    </ul>
  )
}
