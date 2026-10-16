import { compactCurrency, percent } from '../utils/format'

function formatValue(value, format) {
  switch (format) {
    case 'currency':
      return compactCurrency(value)
    case 'percent':
      return percent(value)
    case 'days':
      return `${value.toFixed(1)} days`
    default:
      return Math.round(value).toLocaleString()
  }
}

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

function Change({ kpi, comparisonLabel }) {
  if (kpi.previous === null || kpi.previous === undefined) return null
  const change = describeChange(kpi)
  if (!change) return null
  const { flat } = change
  // higher_is_better is null for neutral measures such as claim volume
  const judged = kpi.higher_is_better !== null && !flat
  const improved = kpi.higher_is_better ? change.delta > 0 : change.delta < 0
  const tone = !judged ? 'text-gray-600' : improved ? 'text-emerald-700' : 'text-red-700'
  const arrow = flat ? '→' : change.delta > 0 ? '▲' : '▼'
  return (
    <div className="text-xs">
      <span className={`font-semibold ${tone}`}>
        <span aria-hidden="true">{arrow}</span> {flat ? 'No change' : change.text}
        <span className="sr-only">
          {flat ? '' : `, ${change.delta > 0 ? 'up' : 'down'}`}
          {judged ? ` (${improved ? 'better' : 'worse'})` : ''}
        </span>
      </span>{' '}
      <span className="text-gray-500">vs {comparisonLabel}</span>
    </div>
  )
}

export default function KpiCard({ kpi, comparisonLabel }) {
  return (
    <div className="flex flex-col gap-1 rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
      <div className="text-sm font-medium text-gray-500">{kpi.label}</div>
      <div className="text-2xl font-bold tabular-nums text-gray-900">
        {formatValue(kpi.value, kpi.format)}
      </div>
      <Change kpi={kpi} comparisonLabel={comparisonLabel} />
      {kpi.detail && <div className="text-xs text-gray-500">{kpi.detail}</div>}
    </div>
  )
}
