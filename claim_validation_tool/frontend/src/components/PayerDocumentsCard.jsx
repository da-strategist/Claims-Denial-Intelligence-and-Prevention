import { useId, useState } from 'react'
import { INPUT_CLASS } from '../constants'
import { deletePayerDocument, payerDocumentFileUrl, uploadPayerDocument } from '../services/api'
import { pageCount, readBase64 } from '../utils/files'
import Icon from './Icon'

const ACCEPT = '.pdf,.txt,.md'
const MAX_MB = 15

const day = (value) =>
  new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })


function DocumentRow({ document, payerName, citedBy, onRemoved }) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const remove = async () => {
    setBusy(true)
    setError(null)
    try {
      await deletePayerDocument(document.id)
      onRemoved()
    } catch (err) {
      setError(err.message)
      setBusy(false)
      setConfirming(false)
    }
  }
  return (
    <li className="py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 text-sm">
          <p className="font-medium text-gray-900">
            {document.title}
            <span className="ml-2 text-xs font-normal text-gray-400">{document.id}</span>
          </p>
          <p className="text-xs text-gray-500">
            {payerName} · {pageCount(document)}
            {document.effective_date && ` · Effective ${day(document.effective_date)}`} · Added{' '}
            {day(document.uploaded_at)} by {document.uploaded_by}
          </p>
          {document.pages_with_text === 0 && (
            <p className="mt-1 text-xs text-amber-800">
              No text could be read (a scanned copy?), so the assistant can’t search it. Rules can still cite it.
            </p>
          )}
          {citedBy.length > 0 && (
            <p className="mt-1 text-xs text-gray-500">Cited by {citedBy.join(', ')}</p>
          )}
        </div>
        {confirming ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-gray-700">Delete this document?</span>
            <button type="button" className="btn-danger btn-sm" disabled={busy} onClick={remove}>
              Delete
            </button>
            <button type="button" className="btn-secondary btn-sm" onClick={() => setConfirming(false)}>
              Keep it
            </button>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            <a className="btn-secondary btn-sm" href={payerDocumentFileUrl(document.id)} download>
              Download
            </a>
            <button
              type="button"
              className="btn-secondary btn-sm"
              onClick={() => setConfirming(true)}
              aria-label={`Delete ${document.title}`}
            >
              Delete
            </button>
          </div>
        )}
      </div>
      {error && (
        <p role="alert" className="mt-1 text-sm text-red-700">
          Could not delete — {error}
        </p>
      )}
    </li>
  )
}

function UploadForm({ payers, onUploaded }) {
  const ids = useId()
  const [file, setFile] = useState(null)
  const [payerId, setPayerId] = useState('')
  const [title, setTitle] = useState('')
  const [effective, setEffective] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [inputKey, setInputKey] = useState(0)

  const choose = (event) => {
    const chosen = event.target.files?.[0] ?? null
    setFile(chosen)
    setError(chosen && chosen.size > MAX_MB * 1024 * 1024 ? `The file is larger than ${MAX_MB} MB` : null)
    if (chosen && !title) setTitle(chosen.name.replace(/\.[^.]+$/, ''))
  }

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const content = await readBase64(file)
      await uploadPayerDocument({
        payer_id: payerId,
        title: title.trim(),
        effective_date: effective || null,
        filename: file.name,
        content,
      })
      setFile(null)
      setTitle('')
      setEffective('')
      setInputKey((key) => key + 1)
      onUploaded()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const tooLarge = file && file.size > MAX_MB * 1024 * 1024
  return (
    <form onSubmit={submit} aria-label="Upload a payer document" className="space-y-3 rounded-xl bg-gray-50 p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor={`${ids}-file`} className="mb-1 block text-sm font-medium text-gray-800">
            File <span className="font-normal text-gray-400">PDF or text, up to {MAX_MB} MB</span>
          </label>
          <input
            key={inputKey}
            id={`${ids}-file`}
            type="file"
            accept={ACCEPT}
            onChange={choose}
            className="block w-full text-sm text-gray-700 file:mr-3 file:rounded-full file:border-0 file:bg-white file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-gray-800 file:ring-1 file:ring-gray-200"
          />
        </div>
        <div>
          <label htmlFor={`${ids}-payer`} className="mb-1 block text-sm font-medium text-gray-800">
            Payer
          </label>
          <select
            id={`${ids}-payer`}
            required
            className={INPUT_CLASS}
            value={payerId}
            onChange={(e) => setPayerId(e.target.value)}
          >
            <option value="">Select…</option>
            {payers.map((payer) => (
              <option key={payer.payer_id} value={payer.payer_id}>
                {payer.payer_name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={`${ids}-title`} className="mb-1 block text-sm font-medium text-gray-800">
            Title
          </label>
          <input
            id={`${ids}-title`}
            required
            maxLength={150}
            placeholder="e.g. Provider manual 2026"
            className={INPUT_CLASS}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor={`${ids}-effective`} className="mb-1 block text-sm font-medium text-gray-800">
            Effective date <span className="font-normal text-gray-400">optional</span>
          </label>
          <input
            id={`${ids}-effective`}
            type="date"
            className={INPUT_CLASS}
            value={effective}
            onChange={(e) => setEffective(e.target.value)}
          />
        </div>
      </div>
      <p className="text-xs text-gray-500">
        Payer documents only: manuals, policies, prior authorization lists. Don’t upload anything with patient
        information.
      </p>
      {error && (
        <p role="alert" className="text-sm text-red-700">
          Could not upload — {error}
        </p>
      )}
      <button type="submit" className="btn-primary btn-sm" disabled={busy || !file || tooLarge}>
        <Icon name="plus" className="h-4 w-4" strokeWidth={2} />
        {busy ? 'Uploading…' : 'Upload document'}
      </button>
    </form>
  )
}

/**
 * The payer's own documents behind payer-specific rules. Rules cite a page; the assistant
 * searches them and cites them by page.
 */
export default function PayerDocumentsCard({ documents, error, reload, payers, rules }) {
  const [adding, setAdding] = useState(false)
  const options = Object.values(payers ?? {}).filter((payer) => payer.payer_type !== 'Self-Pay')
  const citing = (documentId) =>
    (rules ?? []).filter((rule) => rule.source?.document_id === documentId).map((rule) => rule.id)

  return (
    <section aria-labelledby="payer-documents-title" className="card space-y-4 p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="payer-documents-title" className="text-lg font-semibold tracking-tight text-gray-900">
            Payer documents
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-gray-600">
            Upload a payer’s manual, policy or prior authorization list. A rule can cite the page it’s based on,
            flagged claims show that source, and the assistant searches these documents too.
          </p>
        </div>
        {!adding && (
          <button type="button" className="btn-secondary btn-sm" onClick={() => setAdding(true)}>
            <Icon name="plus" className="h-4 w-4" strokeWidth={2} />
            Add document
          </button>
        )}
      </div>

      {adding && (
        <UploadForm
          payers={options}
          onUploaded={() => {
            setAdding(false)
            reload()
          }}
        />
      )}

      {error && (
        <p role="alert" className="text-sm text-red-700">
          Could not load the documents — {error}
        </p>
      )}
      {documents && documents.length === 0 && !adding && (
        <p className="text-sm text-gray-500">No documents yet.</p>
      )}
      {documents && documents.length > 0 && (
        <ul className="divide-y divide-gray-100">
          {documents.map((document) => (
            <DocumentRow
              key={document.id}
              document={document}
              payerName={payers?.[document.payer_id]?.payer_name ?? document.payer_id}
              citedBy={citing(document.id)}
              onRemoved={reload}
            />
          ))}
        </ul>
      )}
    </section>
  )
}
