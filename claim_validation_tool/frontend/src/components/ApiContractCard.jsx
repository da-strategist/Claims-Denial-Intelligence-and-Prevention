import { useId, useState } from 'react'

const DIRECTIONS = {
  outbound: { label: 'ClaustraRCM → JAB Audit', style: 'bg-accent-soft text-accent border-transparent' },
  inbound: { label: 'JAB Audit → ClaustraRCM', style: 'bg-gray-100 text-gray-700 border-transparent' },
}

const TABS = [
  { id: 'fields', label: 'Fields' },
  { id: 'example', label: 'Example' },
  { id: 'schema', label: 'JSON Schema' },
]

function FieldsTable({ fields }) {
  return (
    <div className="relative max-h-96 overflow-auto rounded-lg border border-gray-100">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-gray-50">
          <tr className="text-left eyebrow">
            <th scope="col" className="px-3 py-2">Field</th>
            <th scope="col" className="px-3 py-2">Type</th>
            <th scope="col" className="px-3 py-2">Notes</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((field) => {
            const depth = field.path.split('.').length - 1
            return (
              <tr key={field.path} className="border-t border-gray-100 align-top">
                <td className="whitespace-nowrap px-3 py-1.5 font-mono text-xs text-gray-900">
                  <span style={{ paddingLeft: `${depth}rem` }}>{field.path}</span>
                  {field.required && (
                    <span className="ml-1 text-red-600" title="Required">
                      *<span className="sr-only"> required</span>
                    </span>
                  )}
                </td>
                <td className="whitespace-nowrap px-3 py-1.5 font-mono text-xs text-gray-500">
                  {field.type}
                </td>
                <td className="min-w-48 px-3 py-1.5 text-xs text-gray-600">
                  {field.description}
                  {field.allowed_values && (
                    <div className="font-mono text-gray-500">{field.allowed_values.join(' · ')}</div>
                  )}
                  {field.pattern && (
                    <div className="font-mono text-gray-400">pattern {field.pattern}</div>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function JsonBlock({ value }) {
  return (
    <pre className="max-h-96 overflow-auto rounded-lg bg-gray-900 p-3 text-xs leading-relaxed text-gray-100">
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

/** One proposed API contract: endpoint, purpose, and request payload as fields, example, or schema. */
export default function ApiContractCard({ contract }) {
  const [tab, setTab] = useState('fields')
  const baseId = useId()
  const direction = DIRECTIONS[contract.direction]

  return (
    <section
      id={`contract-${contract.id}`}
      aria-labelledby={`${baseId}-title`}
      className="scroll-mt-4 space-y-3 card p-5"
    >
      <div className="flex flex-wrap items-center gap-2">
        <h3 id={`${baseId}-title`} className="font-semibold text-gray-900">
          {contract.title}
        </h3>
        <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${direction.style}`}>
          {direction.label}
        </span>
      </div>
      <div className="flex min-w-0 items-center gap-2 font-mono text-sm">
        <span className="rounded bg-gray-900 px-1.5 py-0.5 text-xs font-bold text-white">
          {contract.method}
        </span>
        <span className="break-all text-gray-800">{contract.path}</span>
      </div>
      <p className="text-sm text-gray-700">{contract.purpose}</p>
      {contract.notes.length > 0 && (
        <ul className="list-disc space-y-0.5 pl-5 text-sm text-gray-600">
          {contract.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}

      <div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div role="tablist" aria-label={`${contract.title} payload`} className="flex gap-1">
            {TABS.map(({ id, label }) => (
              <button
                key={id}
                type="button"
                role="tab"
                id={`${baseId}-tab-${id}`}
                aria-selected={tab === id}
                aria-controls={`${baseId}-panel`}
                onClick={() => setTab(id)}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium ${tab === id ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-100'}`}
              >
                {label}
              </button>
            ))}
          </div>
          <span className="font-mono text-xs text-gray-500">
            {contract.request_model}
            {contract.response_model && ` → ${contract.response_model}`}
          </span>
        </div>
        <div
          role="tabpanel"
          id={`${baseId}-panel`}
          aria-labelledby={`${baseId}-tab-${tab}`}
          className="mt-2"
        >
          {tab === 'fields' && <FieldsTable fields={contract.request_fields} />}
          {tab === 'example' && <JsonBlock value={contract.request_example} />}
          {tab === 'schema' && <JsonBlock value={contract.request_schema} />}
        </div>
      </div>
    </section>
  )
}
