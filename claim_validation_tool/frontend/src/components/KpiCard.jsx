import { formatKpiValue, percent } from '../utils/format'

/** Change since the comparison period: percentage points for rates, relative % otherwise. */
function describeChange(kpi) {
  const { value, previous, format } = kpi
  if (format === 'percent') {
    const points = (value - previous) * 100
    const text = `${Math.abs(points).toFixed(1)} pts`
    return { delta: points, flat: text === '0.0 pts', text }
  }
  if (format === 'days') {
    const days = value - previous
    const text = `${Math.abs(days).toFixed(1)} days`
    return { delta: days, flat: text === '0.0 days', text }
  }
  if (!previous) return null
  const relative = (value - previous) / previous
  const text = percent(Math.abs(relative))
  return { delta: relative, flat: text === '0.0%', text }
}

/** "▲ 0.3 pts vs prior 12 months", green when better, red when worse, grey when neutral. */
export function Change({ kpi, comparisonLabel }) {
  if (kpi.previous === null || kpi.previous === undefined) return null
  const change = describeChange(kpi)
  if (!change) return null
  const { flat } = change
  // higher_is_better is null for neutral measures such as claim volume
  const judged = kpi.higher_is_better !== null && !flat
  const improved = kpi.higher_is_better ? change.delta > 0 : change.delta < 0
  const tone = !judged ? 'text-gray-500' : improved ? 'text-emerald-700' : 'text-red-700'
  const arrow = flat ? '' : change.delta > 0 ? '↑' : '↓'
  return (
    <div className="text-xs text-gray-500">
      <span className={`font-medium ${tone}`}>
        {arrow && <span aria-hidden="true">{arrow} </span>}
        {flat ? 'Unchanged' : change.text}
        <span className="sr-only">
          {flat ? '' : `, ${change.delta > 0 ? 'up' : 'down'}`}
          {judged ? ` (${improved ? 'better' : 'worse'})` : ''}
        </span>
      </span>{' '}
      vs {comparisonLabel}
    </div>
  )
}

/** One figure in the dashboard's row of measures: label, big number, change, context. */
export default function KpiCard({ kpi, comparisonLabel }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 px-5 py-5">
      <div className="text-[13px] text-gray-500">{kpi.label}</div>
      <div className="text-[28px] leading-tight font-semibold tracking-tight tabular-nums text-gray-900">
        {formatKpiValue(kpi.value, kpi.format)}
        {kpi.format === 'days' && <span className="ml-1 text-base font-normal text-gray-400">days</span>}
      </div>
      <Change kpi={kpi} comparisonLabel={comparisonLabel} />
      {kpi.detail && <div className="mt-1 text-xs leading-relaxed text-gray-400">{kpi.detail}</div>}
    </div>
  )
}
