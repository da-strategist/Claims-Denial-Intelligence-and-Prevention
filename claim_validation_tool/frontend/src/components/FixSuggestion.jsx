import { useId, useState } from 'react'
import { CLARIFICATION_TOPICS, INPUT_CLASS, SUGGESTION_ACTIONS } from '../constants'

const CONFIDENCE_LABELS = { high: 'High confidence', medium: 'Medium confidence', low: 'Needs judgement' }

function formatValue(change, value) {
  if (value === null || value === undefined || value === '') return '—'
  if (change.type === 'boolean') return value === 'true' ? 'Yes' : 'No'
  return value
}

function ChangeInput({ change, value, onChange, inputId }) {
  // Booleans are set by the fix itself; show them as a fixed change
  if (change.type === 'boolean') {
    return (
      <span className="text-sm font-medium text-gray-900">
        {formatValue(change, change.suggested_value)}
      </span>
    )
  }
  const listId = `${inputId}-options`
  return (
    <>
      <input
        id={inputId}
        className={INPUT_CLASS}
        value={value}
        list={change.options ? listId : undefined}
        placeholder={change.requires_input ? `Enter ${change.label.toLowerCase()}` : undefined}
        onChange={(e) => onChange(e.target.value)}
      />
      {change.options && (
        <datalist id={listId}>
          {change.options.map((option) => (
            <option key={option} value={option} />
          ))}
        </datalist>
      )}
    </>
  )
}

function Citations({ citations }) {
  if (citations.length === 0) return null
  return (
    <details className="group text-sm">
      <summary className="cursor-pointer select-none text-xs font-medium text-gray-500 hover:text-gray-800">
        Sources ({citations.length})
      </summary>
      <ul className="mt-2 space-y-1.5">
        {citations.map((citation) => (
          <li
            key={`${citation.source_type}:${citation.reference_id}`}
            className="rounded-md bg-gray-50 px-2.5 py-1.5"
          >
            <div className="text-xs font-semibold text-gray-700">
              {citation.title}
              <span className="ml-1.5 font-normal uppercase tracking-wide text-gray-400">
                {citation.source_type.replace('_', ' ')} · {citation.reference_id}
              </span>
            </div>
            <div className="text-xs text-gray-600">{citation.excerpt}</div>
          </li>
        ))}
      </ul>
    </details>
  )
}

/** One AI Fix suggestion: what to do, why, sources, and (if applicable) the fix form. */
export default function FixSuggestion({ suggestion, onApply }) {
  const formId = useId()
  const [values, setValues] = useState(() =>
    Object.fromEntries(suggestion.changes.map((c) => [c.field, c.suggested_value ?? ''])),
  )
  const [applying, setApplying] = useState(false)
  const [error, setError] = useState(null)
  const action = SUGGESTION_ACTIONS[suggestion.action]

  const submit = async (event) => {
    event.preventDefault()
    setApplying(true)
    setError(null)
    try {
      const editable = suggestion.changes.filter((c) => c.type !== 'boolean')
      await onApply(suggestion, Object.fromEntries(editable.map((c) => [c.field, values[c.field]])))
    } catch (err) {
      setError(err.message)
      setApplying(false)
    }
  }

  return (
    <div className="space-y-2.5 rounded-lg border border-violet-100 bg-violet-50/40 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-violet-700">
          ✦ Suggested fix
        </span>
        <span
          className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${action.style}`}
        >
          {action.label}
        </span>
        <span className="text-xs text-gray-500">{CONFIDENCE_LABELS[suggestion.confidence]}</span>
      </div>

      <div>
        <div className="text-sm font-semibold text-gray-900">{suggestion.title}</div>
        <p className="text-sm text-gray-700">{suggestion.summary}</p>
        <p className="mt-1 text-sm text-gray-500">{suggestion.reasoning}</p>
      </div>

      {suggestion.steps.length > 0 && (
        <ol className="list-decimal space-y-0.5 pl-5 text-sm text-gray-700">
          {suggestion.steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      )}

      <Citations citations={suggestion.citations} />

      {suggestion.action === 'apply' && (
        <form onSubmit={submit} className="space-y-2 border-t border-violet-100 pt-2.5">
          {suggestion.changes.map((change) => {
            const inputId = `${formId}-${change.field}`
            return (
              <div
                key={change.field}
                className="grid items-center gap-x-3 gap-y-1 sm:grid-cols-[10rem_1fr]"
              >
                <label htmlFor={inputId} className="text-sm text-gray-600">
                  {change.label}
                  <span className="block text-xs text-gray-400">
                    now {formatValue(change, change.current_value)}
                  </span>
                </label>
                <ChangeInput
                  change={change}
                  inputId={inputId}
                  value={values[change.field]}
                  onChange={(value) => setValues((prev) => ({ ...prev, [change.field]: value }))}
                />
              </div>
            )
          })}
          {error && (
            <p role="alert" className="text-sm text-red-700">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={applying}
            className="rounded-lg bg-violet-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-violet-700 disabled:opacity-50"
          >
            {applying ? 'Applying…' : 'Apply fix & re-validate'}
          </button>
        </form>
      )}

      {suggestion.needs_clarification && (
        <div className="flex flex-wrap items-center gap-2 border-t border-violet-100 pt-2.5">
          <button
            type="button"
            disabled
            title="The RAG clarification assistant arrives in Phase 10"
            className="cursor-not-allowed rounded-lg border border-sky-200 bg-white px-3 py-1.5 text-sm font-medium text-sky-700 opacity-60"
          >
            Ask the assistant
          </button>
          <span className="text-xs text-gray-500">
            {CLARIFICATION_TOPICS[suggestion.clarification_topic]} · coming in Phase 10
          </span>
        </div>
      )}
    </div>
  )
}
