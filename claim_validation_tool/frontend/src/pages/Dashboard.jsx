import { useState } from 'react'
import Icon from '../components/Icon'
import KpiCard, { Change } from '../components/KpiCard'
import PageHeader, { Notice, Page } from '../components/PageHeader'
import {
  ArAgingChart,
  ChartCard,
  ClaimStatusChart,
  DenialReasonsChart,
  PayerTable,
  RevenueTrendChart,
} from '../components/DashboardCharts'
import { DASHBOARD_PERIODS, DEFAULT_DASHBOARD_MONTHS, FIELD_CLASS } from '../constants'
import { useAuth, useCan } from '../hooks/useAuth'
import { usePayerLookup } from '../hooks/useClaims'
import { useDashboard } from '../hooks/useDashboard'
import { useDepartmentLookup } from '../hooks/useRules'
import { dateLabel, formatKpiValue } from '../utils/format'
import { routeHref } from '../utils/route'

function FilterSelect({ label, value, onChange, options }) {
  return (
    <select
      aria-label={label}
      className={`${FIELD_CLASS} max-w-52 py-1.5`}
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

function sortedOptions(lookup, idKey, nameKey) {
  return Object.values(lookup)
    .sort((a, b) => a[nameKey].localeCompare(b[nameKey]))
    .map((item) => [item[idKey], item[nameKey]])
}

function periodSummary(data) {
  if (!data.period) return 'No claims match these filters'
  const range = `${dateLabel(data.period.start)} – ${dateLabel(data.period.end)}`
  if (!data.comparison_period) return `Service dates ${range}`
  return `Service dates ${range}, compared with the period before`
}

function greeting(name) {
  const hour = new Date().getHours()
  const part = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
  const first = name?.split(/\s+/)[0]
  return first ? `${part}, ${first}` : part
}

/** "3 draft claims to finish, 2 with problems": unsubmitted claims waiting on New Claim. */
function DraftsLine({ drafts }) {
  const { claims, with_problems: problems } = drafts
  const noun = claims === 1 ? 'draft claim' : 'draft claims'
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-gray-100 px-6 py-3.5 sm:px-8">
      <p className="flex items-center gap-2 text-sm text-gray-700">
        <span
          aria-hidden="true"
          className={`h-2 w-2 rounded-full ${problems ? 'bg-amber-500' : 'bg-emerald-500'}`}
        />
        {problems
          ? `${claims.toLocaleString()} ${noun} to finish, ${problems.toLocaleString()} with problems`
          : `${claims.toLocaleString()} ${noun} ready to submit`}
      </p>
      <a href="#/new-claim" className="btn-quiet btn-sm">
        Open drafts
        <Icon name="arrow" className="h-4 w-4" />
      </a>
    </div>
  )
}

/** The one number a billing team acts on, and the way to act on it. */
function AttentionHero({ kpi, href, comparisonLabel, drafts }) {
  const count = formatKpiValue(kpi.value, kpi.format)
  return (
    <section aria-label="Claims needing attention" className="card overflow-hidden">
      <div className="flex flex-wrap items-end justify-between gap-6 p-6 sm:p-8">
        <div className="min-w-0">
          <div className="eyebrow">Needs attention</div>
          <p className="mt-2 text-4xl font-semibold tracking-tight text-gray-900 sm:text-5xl">
            <span className="tabular-nums">{count}</span>{' '}
            <span className="text-gray-400">{kpi.value === 1 ? 'claim' : 'claims'}</span>
          </p>
          <p className="mt-2 max-w-xl text-[15px] text-gray-600">
            {kpi.value
              ? `Have validation errors and are likely to be denied as they stand.${kpi.detail ? ` ${kpi.detail}.` : ''}`
              : 'Every claim in this period passes the current rules.'}
          </p>
          <div className="mt-3">
            <Change kpi={kpi} comparisonLabel={comparisonLabel} />
          </div>
        </div>
        {kpi.value > 0 && (
          <a href={href} className="btn-primary px-5 py-2.5">
            Review claims
            <Icon name="arrow" className="h-4 w-4" />
          </a>
        )}
      </div>
      {drafts?.claims > 0 && <DraftsLine drafts={drafts} />}
    </section>
  )
}

function Skeleton({ className }) {
  return <div className={`card animate-pulse ${className}`} />
}

export default function Dashboard() {
  const { user } = useAuth() ?? {}
  const canEnterClaims = useCan('claims:write')
  const [filters, setFilters] = useState({
    months: DEFAULT_DASHBOARD_MONTHS,
    payer_id: '',
    department_id: '',
  })
  const { data, loading, error } = useDashboard(filters)
  const payers = usePayerLookup()
  const departments = useDepartmentLookup()
  const updateFilters = (changes) => setFilters((prev) => ({ ...prev, ...changes }))
  const comparisonLabel = filters.months ? `prior ${filters.months} months` : 'prior period'

  const atRisk = data?.kpis.find((kpi) => kpi.key === 'at_risk')
  const measures = data?.kpis.filter((kpi) => kpi.key !== 'at_risk') ?? []
  const queueHref = routeHref('#/claims', {
    attention: '1',
    ...(data?.period && { from: data.period.start, to: data.period.end }),
    ...(filters.payer_id && { payer_id: filters.payer_id }),
    ...(filters.department_id && { department_id: filters.department_id }),
  })

  return (
    <Page>
      <PageHeader
        title={greeting(user?.display_name)}
        subtitle={data ? periodSummary(data) : 'Revenue cycle at a glance'}
      >
        <FilterSelect
          label="Period"
          value={filters.months}
          onChange={(months) => updateFilters({ months: months === '' ? '' : Number(months) })}
          options={DASHBOARD_PERIODS.map((period) => [period.months, period.label])}
        />
        <FilterSelect
          label="Payer"
          value={filters.payer_id}
          onChange={(payer_id) => updateFilters({ payer_id })}
          options={[['', 'All payers'], ...sortedOptions(payers, 'payer_id', 'payer_name')]}
        />
        <FilterSelect
          label="Department"
          value={filters.department_id}
          onChange={(department_id) => updateFilters({ department_id })}
          options={[
            ['', 'All departments'],
            ...sortedOptions(departments, 'department_id', 'department_name'),
          ]}
        />
      </PageHeader>

      {error && <Notice>Could not load the dashboard — {error}</Notice>}

      <div
        aria-busy={loading}
        className={`space-y-6 transition-opacity ${loading && data ? 'opacity-60' : ''}`}
      >
        {data ? (
          <>
            {atRisk && (
              <AttentionHero
                kpi={atRisk}
                href={queueHref}
                comparisonLabel={comparisonLabel}
                // Only roles that enter claims can open New Claim to finish them
                drafts={canEnterClaims ? data.drafts : null}
              />
            )}
            <section
              aria-label="Key measures"
              className="card grid grid-cols-1 divide-y divide-gray-100 sm:grid-cols-2 sm:divide-y-0 lg:grid-cols-5 lg:divide-x"
            >
              {measures.map((kpi) => (
                <KpiCard key={kpi.key} kpi={kpi} comparisonLabel={comparisonLabel} />
              ))}
            </section>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              <ChartCard
                className="lg:col-span-2"
                title="Revenue"
                subtitle="Billed, collected, and denied by month of service"
              >
                <RevenueTrendChart data={data.revenue_trend} />
              </ChartCard>
              <ChartCard title="Validation" subtitle="Every claim against the current rules">
                <ClaimStatusChart data={data.validation_status} />
              </ChartCard>
            </div>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <ChartCard title="Why claims are denied" subtitle="Denials by root cause">
                <DenialReasonsChart data={data.denial_reasons} />
              </ChartCard>
              <ChartCard title="AR aging" subtitle="Claims by days in accounts receivable">
                <ArAgingChart data={data.ar_aging} />
              </ChartCard>
            </div>

            <ChartCard title="Payers" subtitle="Ranked by claim volume">
              <PayerTable payers={data.payers} />
            </ChartCard>
          </>
        ) : (
          !error && (
            <>
              <Skeleton className="h-48" />
              <Skeleton className="h-32" />
              <Skeleton className="h-80" />
            </>
          )
        )}
      </div>
    </Page>
  )
}
