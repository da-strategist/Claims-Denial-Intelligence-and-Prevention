import { useId, useState } from 'react'
import { INPUT_CLASS } from '../constants'
import { useApi } from '../hooks/useApi'
import { usePayerLookup } from '../hooks/useClaims'
import { listPriorAuthLists, removePriorAuthList, savePriorAuthList } from '../services/api'

const day = (value) => new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })

/** Codes as pasted from a list or a spreadsheet column: any mix of spaces, commas and new lines. */
const readCodes = (text) => [...new Set(text.toUpperCase().split(/[\s,;]+/).filter(Boolean))]

function ListRow({ list, payerName, onEdit, onRemoved }) {
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const remove = async () => {
    setBusy(true)
    setError(null)
    try {
      await removePriorAuthList(list.payer_id)
      onRemoved()
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }
  const count = list.cpt_codes.length
  return (
    <li className="py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0 text-sm">
          <p className="font-medium text-gray-900">{payerName}</p>
          <p className="text-xs text-gray-500">
            {count} {count === 1 ? 'service' : 'services'} · Updated {day(list.updated_at)} by {list.updated_by}
          </p>
        </div>
        {confirming ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-gray-700">New claims for this payer go back to not assessed.</span>
            <button type="button" className="btn-secondary btn-sm" disabled={busy} onClick={remove}>
              Yes, remove
            </button>
            <button type="button" className="btn-secondary btn-sm" onClick={() => setConfirming(false)}>
              Keep it
            </button>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-secondary btn-sm" onClick={onEdit}>
              Edit
            </button>
            <button type="button" className="btn-secondary btn-sm" onClick={() => setConfirming(true)}>
              Remove
            </button>
          </div>
        )}
      </div>
      {error && (
        <p role="alert" className="mt-1 text-sm text-red-700">
          Could not remove the list — {error}
        </p>
      )}
    </li>
  )
}

/** Which services each payer requires prior authorization for, from the hospital's own lists. */
export default function PriorAuthListsCard() {
  const { data, error, reload } = useApi((options) => listPriorAuthLists(options))
  const payers = usePayerLookup()
  const [payerId, setPayerId] = useState('')
  const [text, setText] = useState('')
  const [problem, setProblem] = useState(null)
  const [busy, setBusy] = useState(false)
  const payerField = useId()
  const codesField = useId()

  if (error) {
    return (
      <section className="card p-6">
        <p role="alert" className="text-sm text-red-700">
          Could not load the prior authorization lists — {error}
        </p>
      </section>
    )
  }
  if (!data) return null

  const codes = readCodes(text)
  const options = Object.values(payers ?? {}).filter((payer) => payer.payer_type !== 'Self-Pay')
  const replacing = data.some((list) => list.payer_id === payerId)

  const save = async (event) => {
    event.preventDefault()
    setBusy(true)
    setProblem(null)
    try {
      await savePriorAuthList(payerId, codes)
      setPayerId('')
      setText('')
      reload()
    } catch (err) {
      setProblem(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-label="Prior authorization lists" className="card space-y-4 p-6">
      <div>
        <h2 className="text-[15px] font-semibold text-gray-900">Prior authorization lists</h2>
        <p className="text-sm text-gray-500">
          The services each payer requires prior authorization for, from your own payer lists. A claim for a listed
          service with no authorization on it is flagged. Claims for a payer with no list show prior auth as not
          assessed. Claims already saved don’t change until they’re edited or sent again.
        </p>
      </div>
      {data.length > 0 && (
        <ul className="divide-y divide-gray-100">
          {data.map((list) => (
            <ListRow
              key={list.payer_id}
              list={list}
              payerName={payers?.[list.payer_id]?.payer_name ?? list.payer_id}
              onEdit={() => {
                setPayerId(list.payer_id)
                setText(list.cpt_codes.join('\n'))
                setProblem(null)
              }}
              onRemoved={reload}
            />
          ))}
        </ul>
      )}
      <form className="space-y-3" onSubmit={save}>
        <label htmlFor={payerField} className="block max-w-sm space-y-1 text-sm font-medium text-gray-800">
          <span className="block">Payer</span>
          <select
            id={payerField}
            className={INPUT_CLASS}
            value={payerId}
            onChange={(event) => setPayerId(event.target.value)}
          >
            <option value="">Choose a payer</option>
            {options.map((payer) => (
              <option key={payer.payer_id} value={payer.payer_id}>
                {payer.payer_name}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor={codesField} className="block space-y-1 text-sm font-medium text-gray-800">
          <span className="block">CPT or HCPCS codes</span>
          <textarea
            id={codesField}
            rows={4}
            className={`${INPUT_CLASS} font-mono`}
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
          <span className="block text-xs font-normal text-gray-500">
            Paste them from your list or a spreadsheet column. Saving replaces the payer’s whole list.
          </span>
        </label>
        <button type="submit" className="btn-primary" disabled={busy || !payerId || codes.length === 0}>
          {replacing ? 'Replace list' : 'Save list'}
          {codes.length > 0 && ` (${codes.length})`}
        </button>
      </form>
      {problem && (
        <p role="alert" className="text-sm text-red-700">
          Could not save the list — {problem}
        </p>
      )}
    </section>
  )
}
