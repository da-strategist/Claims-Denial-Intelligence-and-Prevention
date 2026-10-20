import { Fragment, useState } from 'react'
import ClaimDetailPanel from '../components/ClaimDetailPanel'
import ClaimFilters from '../components/ClaimFilters'
import Icon from '../components/Icon'
import PageHeader, { AccessNote, Notice, Page } from '../components/PageHeader'
import Pagination from '../components/Pagination'
import RiskScore from '../components/RiskScore'
import { ClaimStatusBadge, ValidationBadge } from '../components/StatusBadge'
import { EMPTY_FILTERS } from '../constants'
import {
  useClaimValidations,
  useClaims,
  useDebouncedValue,
  usePayerLookup,
} from '../hooks/useClaims'
import { useDepartmentLookup } from '../hooks/useRules'
import { useApi } from '../hooks/useApi'
import { listClaims } from '../services/api'
import { currency } from '../utils/format'
import { hashParams } from '../utils/route'

const PAGE_SIZE = 25

// `sort` is the API sort_by field; `firstDesc` is the direction of the first click
// Secondary columns step aside on narrow screens so status, validation, and risk stay
// in view; the expanded row shows them all
const CELL = 'px-2 py-3 sm:px-3'
const FROM_SM = 'hidden sm:table-cell'
const FROM_LG = 'hidden lg:table-cell'
const FROM_XL = 'hidden xl:table-cell'
const FROM_2XL = 'hidden 2xl:table-cell'

// The queue opens riskiest first; the full list newest first
const VIEWS = {
  attention: { label: 'Needs attention', sort: { by: 'risk_score', desc: true } },
  all: { label: 'All claims', sort: { by: 'service_date', desc: true } },
}

const COLUMNS = [
  { label: 'Claim ID', sort: 'claim_id', firstDesc: false },
  { label: 'Service Date', sort: 'service_date', firstDesc: true, hide: FROM_SM },
  { label: 'Patient', hide: FROM_XL },
  { label: 'Payer', hide: FROM_LG },
  { label: 'Type', hide: FROM_2XL },
  { label: 'Status' },
  { label: 'Validation' },
  { label: 'Risk', align: 'right', sort: 'risk_score', firstDesc: true },
  { label: 'Charge', align: 'right', sort: 'total_charge', firstDesc: true, hide: FROM_SM },
  { label: 'Paid', align: 'right', sort: 'total_paid', firstDesc: true, hide: FROM_2XL },
  { label: 'Days in AR', align: 'right', sort: 'days_in_ar', firstDesc: true, hide: FROM_LG },
]
const COLUMN_COUNT = COLUMNS.length + 1 // + expand toggle

function SortableHeader({ column, sort, onSort }) {
  const alignClass = column.align === 'right' ? 'text-right' : 'text-left'
  const headerClass = `${CELL} text-xs font-medium text-gray-500 ${alignClass} ${column.hide ?? ''}`
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
        className={`inline-flex items-center gap-1 hover:text-gray-900 ${active ? 'text-gray-900' : ''}`}
        onClick={() => onSort(column)}
      >
        {column.label}
        <span aria-hidden="true" className={active ? '' : 'text-gray-300'}>
          {active ? (sort.desc ? '↓' : '↑') : ''}
        </span>
      </button>
    </th>
  )
}

function ClaimRow({ claim, payerName, validation, validating, expanded, onToggle }) {
  return (
    <tr
      className={`cursor-pointer border-b border-gray-100 transition-colors hover:bg-gray-50 ${expanded ? 'bg-gray-50' : ''}`}
      onClick={onToggle}
    >
      <td className="w-7 py-3 pl-1 sm:w-10 sm:pl-3">
        <button
          aria-expanded={expanded}
          aria-label={`${expanded ? 'Collapse' : 'Expand'} claim ${claim.claim_id}`}
          className="flex h-6 w-6 items-center justify-center rounded-md text-gray-400 hover:bg-gray-200 hover:text-gray-700"
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
            className="ml-2 rounded-full bg-violet-50 px-1.5 py-0.5 text-[11px] font-medium text-violet-700"
          >
            Corrected
          </span>
        )}
      </td>
      <td className={`${CELL} text-sm text-gray-600 ${FROM_SM}`}>{claim.service_date}</td>
      <td className={`${CELL} text-sm text-gray-600 ${FROM_XL}`}>{claim.patient_id}</td>
      <td
        className={`${CELL} max-w-48 truncate text-sm text-gray-700 ${FROM_LG}`}
        title={payerName ?? claim.payer_id}
      >
        {payerName ?? claim.payer_id}
      </td>
      <td className={`${CELL} text-sm text-gray-600 ${FROM_2XL}`}>{claim.claim_type}</td>
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
      <td className={`${CELL} text-right text-sm tabular-nums text-gray-900 ${FROM_SM}`}>
        {currency.format(claim.total_charge)}
      </td>
      <td className={`${CELL} text-right text-sm tabular-nums text-gray-600 ${FROM_2XL}`}>
        {currency.format(claim.total_paid)}
      </td>
      <td className={`${CELL} text-right text-sm tabular-nums text-gray-600 ${FROM_LG}`}>
        {claim.days_in_ar}
      </td>
    </tr>
  )
}

function MessageRow({ children }) {
  return (
    <tr>
      <td colSpan={COLUMN_COUNT} className="px-4 py-16 text-center text-sm text-gray-500">
        {children}
      </td>
    </tr>
  )
}

/** Filters and view from the link that opened the page. */
function linkedState() {
  const params = hashParams()
  const search = params.get('search') ?? ''
  return {
    // A link to one claim shows it whatever its validation result
    view: params.get('attention') === '1' || (!search && !params.size) ? 'attention' : 'all',
    filters: {
      ...EMPTY_FILTERS,
      search,
      payer_id: params.get('payer_id') ?? '',
      department_id: params.get('department_id') ?? '',
      service_date_from: params.get('from') ?? '',
      service_date_to: params.get('to') ?? '',
    },
  }
}

/** "Needs attention" / "All claims" switch. */
function ViewSwitch({ view, attentionCount, onChange }) {
  return (
    <div role="tablist" aria-label="Claims to show" className="inline-flex rounded-xl bg-gray-200/60 p-1">
      {Object.entries(VIEWS).map(([key, { label }]) => {
        const active = view === key
        return (
          <button
            key={key}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(key)}
            className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors ${
              active ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            {label}
            {key === 'attention' && attentionCount !== undefined && (
              <span
                className={`rounded-full px-1.5 text-xs tabular-nums ${attentionCount ? 'bg-red-50 text-red-700' : 'bg-gray-100 text-gray-500'}`}
              >
                {attentionCount.toLocaleString()}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

export default function ClaimsWorkbench() {
  // #/claims?search=CLM0120001 opens the workbench on that claim, expanded;
  // #/claims?attention=1&from=…&to=… opens the queue for a dashboard period
  const [linked] = useState(linkedState)
  const linkedSearch = linked.filters.search
  const [view, setView] = useState(linked.view)
  const [filters, setFilters] = useState(linked.filters)
  const [sort, setSort] = useState(VIEWS[linked.view].sort)
  const [expanded, setExpanded] = useState(
    () => new Set(/^CLM\d{7}$/.test(linkedSearch) ? [linkedSearch] : []),
  )

  // The page belongs to the query it was chosen for: when the (debounced) search,
  // filters, or sort change, we're back on page 1 without an extra request.
  const search = useDebouncedValue(filters.search.trim())
  const query = {
    ...filters,
    search,
    // Drafts are finished on the New Claim page, not here
    include_drafts: false,
    needs_attention: view === 'attention' ? true : '',
    sort_by: sort.by,
    sort_desc: sort.desc,
  }
  const queryKey = JSON.stringify(query)
  const [paging, setPaging] = useState({ queryKey, page: 1 })
  const page = paging.queryKey === queryKey ? paging.page : 1
  const setPage = (nextPage) => setPaging({ queryKey, page: nextPage })

  const { data, loading, error, reload } = useClaims({ ...query, page, page_size: PAGE_SIZE })
  const claims = data?.items ?? []
  const validations = useClaimValidations(claims.map((claim) => claim.claim_id))
  const payers = usePayerLookup()
  const departments = useDepartmentLookup()
  // Size of the queue under the same filters, for the switch
  const { data: attention } = useClaims({ ...query, needs_attention: true, page: 1, page_size: 1 })
  // When the queue comes up empty under filters, how many claims those filters match in
  // All claims (e.g. Pending: submitted claims never have errors, so they're never queued)
  const queueEmpty = view === 'attention' && data?.total === 0
  const elsewhere = useApi(
    (options) =>
      queueEmpty
        ? listClaims({ ...query, needs_attention: '', sort_by: 'service_date', page: 1, page_size: 1 }, options)
        : Promise.resolve(null),
    `${queueEmpty}|${queryKey}`,
  )

  const changeView = (next) => {
    setView(next)
    setSort(VIEWS[next].sort)
  }

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
    <Page wide>
      <PageHeader
        title="Claims"
        subtitle="Every claim is checked against the enabled rules and scored for denial risk."
      >
        <ViewSwitch view={view} attentionCount={attention?.total} onChange={changeView} />
      </PageHeader>

      <AccessNote />

      <ClaimFilters
        filters={filters}
        payers={payers}
        departments={departments}
        onChange={updateFilters}
        onClear={() => updateFilters(EMPTY_FILTERS)}
      />

      {error && <Notice>Could not load claims — {error}</Notice>}
      {validations.error && (
        <Notice tone="warning">Could not validate claims — {validations.error}</Notice>
      )}

      <div className="card relative overflow-x-auto">
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
            {data?.items.length === 0 && (
              <MessageRow>
                {view === 'attention' && elsewhere.data?.total > 0 ? (
                  <span className="inline-flex flex-col items-center gap-3">
                    <span>
                      None of these need attention, but{' '}
                      <strong className="font-medium text-gray-900">
                        {elsewhere.data.total.toLocaleString()} claim{elsewhere.data.total === 1 ? '' : 's'}
                      </strong>{' '}
                      match{elsewhere.data.total === 1 ? 'es' : ''} these filters.
                    </span>
                    <button type="button" className="btn-secondary btn-sm" onClick={() => changeView('all')}>
                      Show {elsewhere.data.total === 1 ? 'it' : 'them'} in All claims
                    </button>
                  </span>
                ) : view === 'attention' ? (
                  <span className="inline-flex flex-col items-center gap-2">
                    <span className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
                      <Icon name="check" />
                    </span>
                    <span className="text-[15px] font-medium text-gray-900">Nothing needs attention</span>
                    <span>Every claim matching these filters passes the current rules.</span>
                  </span>
                ) : (
                  'No claims match these filters.'
                )}
              </MessageRow>
            )}
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
    </Page>
  )
}
