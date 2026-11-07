import { useId, useState } from 'react'
import { Notice } from './PageHeader'
import Icon from './Icon'
import RiskScore from './RiskScore'
import { ValidationBadge } from './StatusBadge'
import { claimImportTemplateUrl, importClaims } from '../services/api'
import { readBase64 } from '../utils/files'
import { currency } from '../utils/format'

const ACCEPT = '.csv,.xlsx,.837,.txt,.edi,.x12'


const FILE_TYPES = { csv: 'CSV', xlsx: 'Excel', '837P': '837P', '837I': '837I' }

/** Upload a claims file: each claim in it is saved as a Draft and checked against the
 * rules, and what couldn't be read is listed with the reasons. */
export default function ClaimUpload({ onClose, onImported, onOpenClaim }) {
  const inputId = useId()
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  const upload = async (event) => {
    event.preventDefault()
    if (!file) return
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const content = await readBase64(file)
      const imported = await importClaims(file.name, content)
      setResult(imported)
      if (imported.created.length > 0) onImported()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-label="Upload claims" className="card mb-6 space-y-5 p-6 sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold text-gray-900">Upload claims</h2>
          <p className="mt-1 text-sm text-gray-500">
            A CSV or Excel file in the template’s layout (one row per service line), or an 837P or 837I
            file. Each claim is saved as a draft and checked against the rules. Nothing is submitted.
            The rules can’t confirm the patient’s coverage is active.
          </p>
        </div>
        <button type="button" className="btn-quiet btn-sm" onClick={onClose} aria-label="Close upload">
          <Icon name="close" className="h-4 w-4" />
        </button>
      </div>

      <form onSubmit={upload} aria-busy={busy} className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          <label htmlFor={inputId} className="mb-1 block text-sm font-medium text-gray-700">
            Claims file
          </label>
          <input
            id={inputId}
            type="file"
            accept={ACCEPT}
            disabled={busy}
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null)
              setResult(null)
              setError(null)
            }}
            className="block w-full text-sm text-gray-700 file:mr-3 file:rounded-lg file:border-0 file:bg-gray-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-gray-800 hover:file:bg-gray-200"
          />
        </div>
        <button type="submit" className="btn-primary" disabled={!file || busy}>
          {busy ? 'Uploading…' : 'Upload and check'}
        </button>
        <a href={claimImportTemplateUrl()} download className="btn-secondary">
          Download CSV template
        </a>
      </form>

      <p className="text-xs text-gray-500">
        In the template, rows with the same claim_ref make one claim; list its diagnoses in one cell,
        primary first, separated by |. Billing details you leave blank come from the patient’s
        registration. For a patient without an ID, use patient_first_name and patient_last_name. 837
        files are matched to your patient list by name and date of birth, to providers by NPI, and to
        payers by ID or name. A patient who isn’t on the list yet is added from the claim.
      </p>

      {error && <Notice>{error}</Notice>}
      {result && <UploadResult result={result} onOpenClaim={onOpenClaim} />}
    </section>
  )
}

function UploadResult({ result, onOpenClaim }) {
  const { created, failed, claims_found: found, file_type: type } = result
  const tone = failed.length === 0 ? 'info' : created.length === 0 ? 'error' : 'warning'
  return (
    <div className="space-y-4">
      <Notice tone={tone}>
        {FILE_TYPES[type] ?? type} file: {created.length} of {found} claim{found === 1 ? '' : 's'} saved as
        drafts
        {failed.length > 0 && `, ${failed.length} couldn’t be saved`}.
        {created.length > 0 && ' Fix any rule findings before submitting.'}
      </Notice>

      {created.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left text-xs font-medium text-gray-500">
                <th className="py-2 pr-3 font-medium">In the file</th>
                <th className="py-2 pr-3 font-medium">Claim</th>
                <th className="py-2 pr-3 font-medium">Patient</th>
                <th className="py-2 pr-3 text-right font-medium">Charge</th>
                <th className="py-2 pr-3 font-medium">Check</th>
                <th className="py-2 text-right font-medium">Risk</th>
              </tr>
            </thead>
            <tbody>
              {created.map((item) => (
                <tr key={item.claim.claim_id} className="border-b border-gray-50 align-top">
                  <td className="py-2 pr-3">
                    <div className="font-medium text-gray-900">{item.ref || '—'}</div>
                    <div className="text-xs text-gray-500">{item.where}</div>
                    {item.notes.map((note) => (
                      <div key={note} className="mt-1 text-xs text-amber-800">
                        {note}
                      </div>
                    ))}
                  </td>
                  <td className="py-2 pr-3">
                    <button
                      type="button"
                      className="font-mono text-accent hover:underline"
                      onClick={() => onOpenClaim(item.claim)}
                    >
                      {item.claim.claim_id}
                    </button>
                  </td>
                  <td className="py-2 pr-3 font-mono text-gray-700">{item.claim.patient_id}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{currency.format(item.claim.total_charge)}</td>
                  <td className="py-2 pr-3">
                    <ValidationBadge status={item.validation.status} />
                  </td>
                  <td className="py-2">
                    <RiskScore score={item.validation.risk_score} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {failed.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-gray-900">Couldn’t be saved</h3>
          <ul className="space-y-2">
            {failed.map((item) => (
              <li key={`${item.ref}-${item.where}`} className="rounded-xl bg-red-50 px-4 py-3 text-sm">
                <div className="font-medium text-red-900">
                  {item.ref || 'No claim reference'} <span className="font-normal text-red-700">· {item.where}</span>
                </div>
                <ul className="mt-1 list-disc pl-5 text-red-800">
                  {item.errors.map((message) => (
                    <li key={message}>{message}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
