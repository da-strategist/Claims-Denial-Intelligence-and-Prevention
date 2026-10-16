import { useState } from 'react'
import KpiCard from '../components/KpiCard'
import {
  ArAgingChart,
  ChartCard,
  ClaimStatusChart,
  DenialReasonsChart,
  PayerTable,
  RevenueTrendChart,
} from '../components/DashboardCharts'
import { DASHBOARD_PERIODS, FIELD_CLASS } from '../constants'
import { usePayerLookup } from '../hooks/useClaims'
import { useDashboard } from '../hooks/useDashboard'
import { useDepartmentLookup } from '../hooks/useRules'
import { dateLabel } from '../utils/format'

function FilterSelect({ label, value, onChange, options }) {
  return (
    <select
      aria-label={label}
      className={FIELD_CLASS}
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

function PeriodSummary({ data }) {
  if (!data.period) return 'No claims match these filters'
  const range = `${dateLabel(data.period.start)} – ${dateLabel(data.period.end)}`
  if (!data.comparison_period) return `Service dates ${range}`
  return `Service dates ${range}, compared with ${dateLabel(data.comparison_period.start)} – ${dateLabel(data.comparison_period.end)}`
}

function KpiSkeleton() {
  return <div className="h-32 animate-pulse rounded-xl border border-gray-100 bg-white shadow-sm" />
}

export default function Dashboard() {
  const [filters, setFilters] = useState({ months: 12, payer_id: '', department_id: '' })
  const { data, loading, error } = useDashboard(filters)
  const payers = usePayerLookup()
  const departments = useDepartmentLookup()
  const updateFilters = (changes) => setFilters((prev) => ({ ...prev, ...changes }))
  const comparisonLabel = `prior ${filters.months} months`

  return (
    <div className="space-y-4 p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Executive Dashboard</h1>
          <p className="text-sm text-gray-500">
            {data ? <PeriodSummary data={data} /> : 'Revenue cycle performance at a glance'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
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
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          Could not load the dashboard — {error}
        </div>
      )}

      <div
        aria-busy={loading}
        className={`space-y-4 transition-opacity ${loading && data ? 'opacity-60' : ''}`}
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
          {data
            ? data.kpis.map((kpi) => (
                <KpiCard key={kpi.key} kpi={kpi} comparisonLabel={comparisonLabel} />
              ))
            : Array.from({ length: 6 }, (_, index) => <KpiSkeleton key={index} />)}
        </div>

        {data && (
          <>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <ChartCard
                className="lg:col-span-2"
                title="Revenue Trends"
                subtitle="Billed, collected, and denied amounts by month of service"
              >
                <RevenueTrendChart data={data.revenue_trend} />
              </ChartCard>
              <ChartCard
                title="Claim Validation Status"
                subtitle="Every claim checked against the current rules"
              >
                <ClaimStatusChart data={data.validation_status} />
              </ChartCard>
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <ChartCard title="Top Denial Reasons" subtitle="Denials by root cause">
                <DenialReasonsChart data={data.denial_reasons} />
              </ChartCard>
              <ChartCard title="AR Aging" subtitle="Claims by days in accounts receivable">
                <ArAgingChart data={data.ar_aging} />
              </ChartCard>
            </div>

            <ChartCard title="Payer Performance" subtitle="Ranked by claim volume">
              <PayerTable payers={data.payers} />
            </ChartCard>
          </>
        )}
      </div>
    </div>
  )
}
