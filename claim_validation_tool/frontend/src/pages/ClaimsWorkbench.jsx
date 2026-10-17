import { Fragment, useState } from 'react'
import ClaimDetailPanel from '../components/ClaimDetailPanel'
import ClaimFilters from '../components/ClaimFilters'
import Pagination from '../components/Pagination'
import RiskScore from '../components/RiskScore'
import { ClaimStatusBadge, ValidationBadge } from '../components/StatusBadge'
import { EMPTY_FILTERS, VALIDATION_STATUSES } from '../constants'
import {
  useClaimValidations,
  useClaims,
  useDebouncedValue,
  usePayerLookup,
} from '../hooks/useClaims'
import { currency } from '../utils/format'
import { hashParams } from '../utils/route'

const PAGE_SIZE = 25

// `sort` is the API sort_by field; `firstDesc` is the direction of the first click
// Secondary columns step aside on narrow screens so status, validation, and risk stay
// in view; the expanded row shows them all
const CELL = 'px-2 py-3 sm:px-4'
const FROM_SM = 'hidden sm:table-cell'
const FROM_LG = 'hidden lg:table-cell'

const COLUMNS = [
  { label: 'Claim ID', sort: 'claim_id', firstDesc: false },
  { label: 'Service Date', sort: 'service_date', firstDesc: true, hide: FROM_SM },
  { label: 'Patient', hide: FROM_LG },
  { label: 'Payer', hide: FROM_LG },
  { label: 'Type', hide: FROM_LG },
  { label: 'Status' },
  { label: 'Validation' },
  { label: 'Risk', align: 'right' },
  { label: 'Charge', align: 'right', sort: 'total_charge', firstDesc: true, hide: FROM_SM },
  { label: 'Paid', align: 'right', sort: 'total_paid', firstDesc: true, hide: FROM_LG },
  { label: 'Days in AR', align: 'right', sort: 'days_in_ar', firstDesc: true, hide: FROM_LG },
]
const COLUMN_COUNT = COLUMNS.length + 1 // + expand toggle

function SortableHeader({ column, sort, onSort }) {
  const alignClass = column.align === 'right' ? 'text-right' : 'text-left'
  const headerClass = `${CELL} text-xs font-semibold uppercase text-gray-500 ${alignClass} ${column.hide ?? ''}`
  if (!column.sort) {
    return (
      <th scope="col" className={headerClass}>
        {column.label}
      </th>
    )
  }
  const active = sort.by === column.sort
  return (
    <th
      scope="col"
      className={headerClass}
      aria-sort={active ? (sort.desc ? 'descending' : 'ascending') : 'none'}
    >
      <button
        className={`inline-flex items-center gap-1 uppercase hover:text-gray-900 ${active ? 'text-gray-900' : ''}`}
        onClick={() => onSort(column)}
      >
        {column.label}
        <span aria-hidden="true" className={active ? '' : 'text-gray-300'}>
          {active ? (sort.desc ? '↓' : '↑') : '↕'}
        </span>
      </button>
    </th>
  )
}

function ClaimRow({ claim, payerName, validation, validating, expanded, onToggle }) {
  return (
    <tr
      className={`cursor-pointer border-b border-gray-50 hover:bg-gray-50 ${expanded ? 'bg-gray-50' : ''}`}
      onClick={onToggle}
    >
      <td className="w-7 py-3 pl-1 sm:w-10 sm:pl-4">
        <button
          aria-expanded={expanded}
          aria-label={`${expanded ? 'Collapse' : 'Expand'} claim ${claim.claim_id}`}
          className="flex h-6 w-6 items-center justify-center rounded text-gray-400 hover:bg-gray-200 hover:text-gray-700"
          onClick={(event) => {
            event.stopPropagation()
            onToggle()
          }}
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="h-4 w-4 transition-transform"
            // Inline rather than Tailwind's rotate-90, which applies both `rotate` and
            // `transform` here and turns the chevron 180°
            style={{ transform: expanded ? 'rotate(90deg)' : 'none' }}
          >
            <path
              fillRule="evenodd"
              d="M7.2 14.8a.75.75 0 0 1 0-1.06L10.94 10 7.2 6.26a.75.75 0 1 1 1.06-1.06l4.27 4.27a.75.75 0 0 1 0 1.06l-4.27 4.27a.75.75 0 0 1-1.06 0Z"
              clipRule="evenodd"
            />
          </svg>
        </button>
      </td>
      <td className={`${CELL} text-sm font-medium text-gray-900`}>
        {claim.claim_id}
        {claim.has_corrections && (
          <span
            title="AI Fix corrections applied"
            className="ml-2 rounded-full bg-violet-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-700"
          >
            Corrected
          </span>
        )}
      </td>
      <td className={`${CELL} text-sm text-gray-600 ${FROM_SM}`}>{claim.service_date}</td>
      <td className={`${CELL} text-sm text-gray-600 ${FROM_LG}`}>{claim.patient_id}</td>
      <td
        className={`${CELL} max-w-48 truncate text-sm text-gray-700 ${FROM_LG}`}
        title={payerName ?? claim.payer_id}
      >
        {payerName ?? claim.payer_id}
      </td>
      <td className={`${CELL} text-sm text-gray-600 ${FROM_LG}`}>{claim.claim_type}</td>
      <td className={CELL}>
        <ClaimStatusBadge status={claim.status} overdue={claim.is_overdue} />
      </td>
      <td className={CELL}>
        {validation ? (
          <ValidationBadge status={validation.status} />
        ) : (
          <span className="text-xs text-gray-400">{validating ? 'Validating…' : '—'}</span>
        )}
      </td>
      <td className={CELL}>
        <RiskScore score={validation?.risk_score} />
      </td>
      <td className={`${CELL} text-right text-sm font-medium tabular-nums text-gray-900 ${FROM_SM}`}>
        {currency.format(claim.total_charge)}
      </td>
      <td className={`${CELL} text-right text-sm tabular-nums text-gray-600 ${FROM_LG}`}>
        {currency.format(claim.total_paid)}
      </td>
      <td className={`${CELL} text-right text-sm tabular-nums text-gray-600 ${FROM_LG}`}>
        {claim.days_in_ar}
      </td>
    </tr>
  )
}

/** Counts of each validation status on the current page. */
function PageSummary({ claims, validations }) {
  const counts = {}
  for (const claim of claims) {
    const status = validations[claim.claim_id]?.status
    if (status) counts[status] = (counts[status] ?? 0) + 1
  }
  const entries = Object.keys(VALIDATION_STATUSES).filter((status) => counts[status])
  if (entries.length === 0) return null
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm text-gray-500">
      <span>This page:</span>
      {entries.map((status) => (
        <span key={status} className="inline-flex items-center gap-1">
          <ValidationBadge status={status} />
          <span className="tabular-nums text-gray-700">{counts[status]}</span>
        </span>
      ))}
    </div>
  )
}

function MessageRow({ children }) {
  return (
    <tr>
      <td colSpan={COLUMN_COUNT} className="px-4 py-10 text-center text-sm text-gray-500">
        {children}
      </td>
    </tr>
  )
}

export default function ClaimsWorkbench() {
  // #/claims?search=CLM0120001 opens the workbench on that claim, expanded
  const [linkedSearch] = useState(() => hashParams().get('search') ?? '')
  const [filters, setFilters] = useState({ ...EMPTY_FILTERS, search: linkedSearch })
  const [sort, setSort] = useState({ by: 'service_date', desc: true })
  const [expanded, setExpanded] = useState(
    () => new Set(/^CLM\d{7}$/.test(linkedSearch) ? [linkedSearch] : []),
  )

  // The page belongs to the query it was chosen for: when the (debounced) search,
  // filters, or sort change, we're back on page 1 without an extra request.
  const search = useDebouncedValue(filters.search.trim())
  const query = { ...filters, search, sort_by: sort.by, sort_desc: sort.desc }
  const queryKey = JSON.stringify(query)
  const [paging, setPaging] = useState({ queryKey, page: 1 })
  const page = paging.queryKey === queryKey ? paging.page : 1
  const setPage = (nextPage) => setPaging({ queryKey, page: nextPage })

  const { data, loading, error, reload } = useClaims({ ...query, page, page_size: PAGE_SIZE })
  const claims = data?.items ?? []
  const validations = useClaimValidations(claims.map((claim) => claim.claim_id))
  const payers = usePayerLookup()

  const updateFilters = (changes) => setFilters((prev) => ({ ...prev, ...changes }))

  const handleSort = (column) => {
    setSort((prev) =>
      prev.by === column.sort
        ? { by: prev.by, desc: !prev.desc }
        : { by: column.sort, desc: column.firstDesc },
    )
  }

  const toggleExpanded = (claimId) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(claimId)) next.delete(claimId)
      else next.add(claimId)
      return next
    })
  }

  return (
    <div className="space-y-4 p-4 sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Claims Workbench</h1>
          <p className="text-sm text-gray-500">
            Each claim is checked against the enabled validation rules and scored for denial risk.
          </p>
        </div>
        {data && (
          <div className="text-sm text-gray-500">
            {data.total.toLocaleString()} claim{data.total === 1 ? '' : 's'}
          </div>
        )}
      </div>

      <ClaimFilters
        filters={filters}
        payers={payers}
        onChange={updateFilters}
        onClear={() => updateFilters(EMPTY_FILTERS)}
      />

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          Could not load claims — {error}
        </div>
      )}
      {validations.error && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          Could not validate claims — {validations.error}
        </div>
      )}

      <PageSummary claims={claims} validations={validations.byId} />

      <div className="relative overflow-x-auto rounded-xl border border-gray-100 bg-white shadow-sm">
        <table className={`w-full whitespace-nowrap transition-opacity ${loading && data ? 'opacity-50' : ''}`}>
          <thead>
            <tr className="border-b border-gray-100">
              <th scope="col" className="w-7 sm:w-10">
                <span className="sr-only">Expand</span>
              </th>
              {COLUMNS.map((column) => (
                <SortableHeader key={column.label} column={column} sort={sort} onSort={handleSort} />
              ))}
            </tr>
          </thead>
          <tbody>
            {claims.map((claim) => {
              const isExpanded = expanded.has(claim.claim_id)
              const validation = validations.byId[claim.claim_id]
              return (
                <Fragment key={claim.claim_id}>
                  <ClaimRow
                    claim={claim}
                    payerName={payers[claim.payer_id]?.payer_name}
                    validation={validation}
                    validating={validations.loading}
                    expanded={isExpanded}
                    onToggle={() => toggleExpanded(claim.claim_id)}
                  />
                  {isExpanded && (
                    <tr className="border-b border-gray-100">
                      <td colSpan={COLUMN_COUNT} className="p-0">
                        <ClaimDetailPanel
                          claim={claim}
                          validation={validation}
                          onClaimChanged={() => {
                            reload()
                            validations.reload()
                          }}
                        />
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
            {!data && loading && <MessageRow>Loading claims…</MessageRow>}
            {data?.items.length === 0 && <MessageRow>No claims match these filters.</MessageRow>}
          </tbody>
        </table>
      </div>

      {data && (
        <Pagination
          page={data.page}
          pages={data.pages}
          total={data.total}
          pageSize={data.page_size}
          onPageChange={setPage}
          disabled={loading}
        />
      )}
    </div>
  )
}
