import { CLAIM_STATUSES, EMPTY_FILTERS } from '../constants'

const SELECT_CLASS =
  'rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 focus:border-red-400 focus:outline-none focus:ring-2 focus:ring-red-100'

function FilterSelect({ label, value, onChange, options }) {
  return (
    <select
      aria-label={label}
      className={SELECT_CLASS}
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

/** Search box and filter dropdowns. `onChange` receives the fields that changed. */
export default function ClaimFilters({ filters, payers, onChange, onClear }) {
  const isFiltered = Object.entries(filters).some(([key, value]) => value !== EMPTY_FILTERS[key])
  const payerOptions = Object.values(payers)
    .sort((a, b) => a.payer_name.localeCompare(b.payer_name))
    .map((payer) => [payer.payer_id, payer.payer_name])

  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        type="search"
        aria-label="Search claims"
        placeholder="Search claim ID, patient ID, or ICD-10…"
        className={`${SELECT_CLASS} w-full sm:w-72`}
        value={filters.search}
        onChange={(event) => onChange({ search: event.target.value })}
      />
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
        options={[['', 'Any status'], ...CLAIM_STATUSES.map((status) => [status, status])]}
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
      <label className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700">
        <input
          type="checkbox"
          className="accent-red-600"
          checked={filters.missing_prior_auth === 'true'}
          onChange={(event) => onChange({ missing_prior_auth: event.target.checked ? 'true' : '' })}
        />
        Missing prior auth
      </label>
      <label className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700">
        <input
          type="checkbox"
          className="accent-red-600"
          checked={filters.overdue === 'true'}
          onChange={(event) => onChange({ overdue: event.target.checked ? 'true' : '' })}
        />
        Overdue
      </label>
      {isFiltered && (
        <button
          className="px-2 py-2 text-sm font-medium text-red-700 hover:text-red-800"
          onClick={onClear}
        >
          Clear filters
        </button>
      )}
    </div>
  )
}
