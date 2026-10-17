import { useCan } from '../hooks/useAuth'
import { claim837Url, claimFormPdfUrl, readable837PdfUrl } from '../services/api'

/** The 837 a claim was submitted with: what it is, whether it's live, and a download. */
export default function EdiFileCard({ claimId, edi }) {
  // The file holds the patient's full details, so only roles that change claims get it
  const canDownload = useCan('claims:write')
  if (!edi) return null
  const created = new Date(edi.generated_at).toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
  return (
    <div className="space-y-3 rounded-2xl bg-gray-50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-gray-900">
            {edi.transaction} claim file
            {edi.test ? (
              <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800">Test file</span>
            ) : (
              <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-800">Live</span>
            )}
          </div>
          <div className="text-xs text-gray-500">
            Created {created} · control number {edi.control_number}
          </div>
        </div>
      </div>
      {canDownload && (
        <div className="flex flex-wrap gap-2">
          <a href={claim837Url(claimId)} download className="btn-secondary btn-sm">
            Download 837
          </a>
          <a href={claimFormPdfUrl(claimId)} download className="btn-secondary btn-sm">
            {edi.transaction === '837I' ? 'UB-04' : 'CMS-1500'} PDF
          </a>
          <a href={readable837PdfUrl(claimId)} download className="btn-secondary btn-sm">
            Readable 837 PDF
          </a>
        </div>
      )}
      {edi.test && edi.notes.length > 0 && (
        <p className="text-xs text-gray-600">
          Can’t go to a payer yet. An administrator needs to complete the EDI settings:{' '}
          {edi.notes.join('. ').replace(/^Not set: /, '').replace('. Not set: ', '. ')}.
        </p>
      )}
    </div>
  )
}
