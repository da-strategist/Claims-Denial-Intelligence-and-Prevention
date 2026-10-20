import { CLAIM_STATUSES, EMPTY_FILTERS } from '../constants'
import { dateLabel } from '../utils/format'
import Icon from './Icon'

const SELECT_CLASS = 'field py-1.5 pr-8 text-[13px]'

function FilterSelect({ label, value, onChange, options }) {
  return (
    <select
      aria-label={label}
      className={`${SELECT_CLASS} ${value ? 'border-accent/40 bg-accent-soft/50' : ''}`}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    >
      {options.map(([optionValue, optionLabel]) => (
        <option key={optionValue} value={optionValue}>
          {optionLabel}
        </option>
      ))}
    </select>
  )
}

/** On/off filter shown as a pill. */
function ToggleChip({ label, on, onChange }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={() => onChange(!on)}
      className={`rounded-xl px-3 py-1.5 text-[13px] font-medium ring-1 ring-inset transition-colors ${
        on ? 'bg-accent-soft text-accent ring-accent/30' : 'bg-white text-gray-700 ring-gray-200 hover:bg-gray-50'
      }`}
    >
      {label}
    </button>
  )
}

/** A filter set by a link (no control of its own), with a button to remove it. */
function ScopeChip({ label, onRemove }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-xl bg-gray-900 py-1 pr-1 pl-3 text-[13px] font-medium text-white">
      {label}
      <button
        type="button"
        onClick={onRemove}
        className="rounded-lg p-0.5 text-gray-400 hover:bg-white/10 hover:text-white"
        aria-label={`Remove filter: ${label}`}
      >
        <Icon name="close" className="h-3.5 w-3.5" strokeWidth={2} />
      </button>
    </span>
  )
}

/** Search box and filters. `onChange` receives the fields that changed. */
export default function ClaimFilters({ filters, payers, departments = {}, onChange, onClear }) {
  const isFiltered = Object.entries(filters).some(([key, value]) => value !== EMPTY_FILTERS[key])
  const payerOptions = Object.values(payers)
    .sort((a, b) => a.payer_name.localeCompare(b.payer_name))
    .map((payer) => [payer.payer_id, payer.payer_name])
  const { service_date_from: from, service_date_to: to, department_id } = filters

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="relative w-full sm:w-80">
        <Icon
          name="search"
          className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-gray-400"
        />
        <input
          type="search"
          aria-label="Search claims"
          placeholder="Claim ID, patient ID, or ICD-10"
          className="field w-full py-1.5 pl-9 text-[13px]"
          value={filters.search}
          onChange={(event) => onChange({ search: event.target.value })}
        />
      </div>
      <FilterSelect
        label="Payer"
        value={filters.payer_id}
        onChange={(payer_id) => onChange({ payer_id })}
        options={[['', 'All payers'], ...payerOptions]}
      />
      <FilterSelect
        label="Claim status"
        value={filters.status}
        onChange={(status) => onChange({ status })}
        options={[
          ['', 'Any status'],
          ...CLAIM_STATUSES.filter((status) => status !== 'Draft').map((status) => [status, status]),
        ]}
      />
      <FilterSelect
        label="Claim type"
        value={filters.claim_type}
        onChange={(claim_type) => onChange({ claim_type })}
        options={[
          ['', 'Any type'],
          ['Professional', 'Professional'],
          ['Institutional', 'Institutional'],
        ]}
      />
      <FilterSelect
        label="Clean claim"
        value={filters.is_clean_claim}
        onChange={(is_clean_claim) => onChange({ is_clean_claim })}
        options={[
          ['', 'Clean or not'],
          ['true', 'Clean claims'],
          ['false', 'Non-clean claims'],
        ]}
      />
      <ToggleChip
        label="Missing prior auth"
        on={filters.missing_prior_auth === 'true'}
        onChange={(on) => onChange({ missing_prior_auth: on ? 'true' : '' })}
      />
      <ToggleChip
        label="Overdue"
        on={filters.overdue === 'true'}
        onChange={(on) => onChange({ overdue: on ? 'true' : '' })}
      />
      {(from || to) && (
        <ScopeChip
          label={`${from ? dateLabel(from) : '…'} – ${to ? dateLabel(to) : '…'}`}
          onRemove={() => onChange({ service_date_from: '', service_date_to: '' })}
        />
      )}
      {department_id && (
        <ScopeChip
          label={departments[department_id]?.department_name ?? department_id}
          onRemove={() => onChange({ department_id: '' })}
        />
      )}
      {isFiltered && (
        <button type="button" className="btn-quiet btn-sm" onClick={onClear}>
          Clear
        </button>
      )}
    </div>
  )
}
