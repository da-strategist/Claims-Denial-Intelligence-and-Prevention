import { useApi } from '../hooks/useApi'
import { getHandoffExport, handoff837Url, handoffChangesPdfUrl } from '../services/api'

/** What a handed-off claim takes back to the billing system: its 837 and what changed here. */
export default function HandoffExport({ claimId }) {
  const { data, loading, error } = useApi((options) => getHandoffExport(claimId, options), claimId)

  if (error) {
    return (
      <p role="alert" className="text-sm text-red-700">
        Could not load the export — {error}
      </p>
    )
  }
  if (loading && !data) return <p className="text-sm text-gray-500">Preparing the export…</p>
  if (!data) return null

  const { changes, edi, source_ref: sourceRef } = data
  return (
    <div className="space-y-3 border-t border-gray-100 pt-3">
      <div>
        <h4 className="text-sm font-semibold text-gray-900">Take it back to your billing system</h4>
        {sourceRef && <p className="text-xs text-gray-500">Your claim number: {sourceRef}</p>}
      </div>
      {changes.length === 0 ? (
        <p className="text-sm text-gray-600">Nothing was changed here.</p>
      ) : (
        <ul className="space-y-1 text-sm text-gray-700">
          {changes.map((change) => (
            <li key={change.field} className="flex flex-wrap justify-between gap-x-3">
              <span>
                {change.label}: {change.old_value ?? '—'} → {change.new_value ?? '—'}
              </span>
              <span className="text-xs text-gray-400">
                {change.source}
                {change.changed_by && ` · ${change.changed_by}`}
              </span>
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap gap-2">
        {edi && (
          <a href={handoff837Url(claimId)} download className="btn-secondary btn-sm">
            Download {edi.transaction}
          </a>
        )}
        <a href={handoffChangesPdfUrl(claimId)} download className="btn-secondary btn-sm">
          List of changes (PDF)
        </a>
      </div>
      {edi ? (
        <p className="text-xs text-gray-600">
          The file is a first-time claim, not a replacement, because nothing has reached a payer.
          {edi.test && (
            <span className="text-amber-800">
              {' '}It’s marked as a test file until an administrator completes the claim file settings on the Users page
              {edi.notes.length > 0 && `: ${edi.notes.join('. ').replace(/^Not set: /, '').replace('. Not set: ', '. ')}`}.
            </span>
          )}
        </p>
      ) : (
        <p className="text-xs text-gray-600">Self-pay claims are billed to the patient, so there’s no 837 file.</p>
      )}
    </div>
  )
}
