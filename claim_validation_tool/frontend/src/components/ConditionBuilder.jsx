import { INPUT_CLASS, OPERATOR_LABELS, VALUELESS_OPERATORS } from '../constants'

function ValueInput({ field, value, onChange, label }) {
  const common = { 'aria-label': label, className: INPUT_CLASS, value: value ?? '' }
  switch (field?.type) {
    case 'enum':
      return (
        <select {...common} onChange={(e) => onChange(e.target.value)}>
          <option value="">Select…</option>
          {field.options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      )
    case 'boolean':
      return (
        <select {...common} onChange={(e) => onChange(e.target.value)}>
          <option value="">Select…</option>
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>
      )
    case 'number':
      return (
        <input {...common} type="number" step="any" onChange={(e) => onChange(e.target.value)} />
      )
    case 'date':
      return <input {...common} type="date" onChange={(e) => onChange(e.target.value)} />
    default:
      return (
        <input
          {...common}
          type="text"
          placeholder="Value"
          onChange={(e) => onChange(e.target.value)}
        />
      )
  }
}

function ConditionRow({ condition, index, fieldList, fields, onChange, onRemove, canRemove }) {
  const field = fields[condition.field]
  const operators = field?.operators ?? []

  const changeField = (name) => {
    const next = fields[name]
    const operator = next.operators.includes(condition.operator)
      ? condition.operator
      : next.operators[0]
    onChange({ field: name, operator, value: '' })
  }

  return (
    <div className="grid grid-cols-[1fr_auto] gap-2 sm:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)_auto]">
      <select
        aria-label={`Condition ${index + 1} field`}
        className={INPUT_CLASS}
        value={condition.field}
        onChange={(e) => changeField(e.target.value)}
      >
        {fieldList.map((f) => (
          <option key={f.field} value={f.field}>
            {f.label}
          </option>
        ))}
      </select>
      <button
        type="button"
        aria-label={`Remove condition ${index + 1}`}
        onClick={onRemove}
        disabled={!canRemove}
        className="row-span-3 self-start rounded-lg px-2 py-2 text-gray-400 hover:bg-gray-100 hover:text-red-600 disabled:invisible sm:order-last sm:row-span-1"
      >
        ✕
      </button>
      <select
        aria-label={`Condition ${index + 1} operator`}
        className={INPUT_CLASS}
        value={condition.operator}
        onChange={(e) => onChange({ ...condition, operator: e.target.value })}
      >
        {operators.map((op) => (
          <option key={op} value={op}>
            {OPERATOR_LABELS[op] ?? op}
          </option>
        ))}
      </select>
      {VALUELESS_OPERATORS.has(condition.operator) ? (
        <div className="hidden sm:block" />
      ) : (
        <ValueInput
          field={field}
          value={condition.value}
          label={`Condition ${index + 1} value`}
          onChange={(value) => onChange({ ...condition, value })}
        />
      )}
    </div>
  )
}

/** Edit a rule's conditions (field / operator / value) and how they combine (AND / OR). */
export default function ConditionBuilder({ conditions, logic, fields, onChange, onLogicChange }) {
  const fieldList = Object.values(fields)
  const update = (index, condition) =>
    onChange(conditions.map((c, i) => (i === index ? condition : c)))
  const remove = (index) => onChange(conditions.filter((_, i) => i !== index))
  const add = () => {
    const first = fieldList[0]
    onChange([...conditions, { field: first.field, operator: first.operators[0], value: '' }])
  }

  return (
    <div className="space-y-2">
      {conditions.length > 1 && (
        <div className="flex items-center gap-2 text-sm text-gray-600">
          Flag a claim when
          <div className="inline-flex overflow-hidden rounded-xl border border-gray-200">
            {[
              ['AND', 'all'],
              ['OR', 'any'],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                aria-pressed={logic === value}
                onClick={() => onLogicChange(value)}
                className={`px-3 py-1 text-sm font-medium ${logic === value ? 'bg-gray-900 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
              >
                {label}
              </button>
            ))}
          </div>
          of these conditions are true
        </div>
      )}
      {conditions.map((condition, index) => (
        <div key={index}>
          {index > 0 && (
            <div className="py-1 text-xs font-semibold tracking-wide text-gray-400">{logic}</div>
          )}
          <ConditionRow
            condition={condition}
            index={index}
            fieldList={fieldList}
            fields={fields}
            onChange={(c) => update(index, c)}
            onRemove={() => remove(index)}
            canRemove={conditions.length > 1}
          />
        </div>
      ))}
      <button
        type="button"
        onClick={add}
        disabled={fieldList.length === 0}
        className="text-sm font-medium text-red-700 hover:text-red-800 disabled:opacity-40"
      >
        + Add condition
      </button>
    </div>
  )
}
