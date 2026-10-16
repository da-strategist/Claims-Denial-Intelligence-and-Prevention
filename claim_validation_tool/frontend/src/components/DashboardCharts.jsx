import { useId } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { VALIDATION_STATUSES } from '../constants'
import { compactCurrency, currency, monthLabel, percent } from '../utils/format'

const AXIS_TICK = { fontSize: 12, fill: '#6b7280' }
const count = (value) => value.toLocaleString()
const GRID_STROKE = '#f3f4f6'

/** Titled card for one chart. */
export function ChartCard({ title, subtitle, children, className = '' }) {
  const titleId = useId()
  return (
    <section
      aria-labelledby={titleId}
      className={`min-w-0 rounded-xl border border-gray-100 bg-white p-4 shadow-sm ${className}`}
    >
      <h2 id={titleId} className="font-semibold text-gray-900">
        {title}
      </h2>
      {subtitle && <p className="text-xs text-gray-500">{subtitle}</p>}
      <div className="mt-3">{children}</div>
    </section>
  )
}

function Empty() {
  return (
    <div className="flex h-64 items-center justify-center text-sm text-gray-400">
      No claims in this period
    </div>
  )
}

const REVENUE_SERIES = [
  { key: 'charges', name: 'Billed', color: '#6b7280' },
  { key: 'paid', name: 'Collected', color: '#10b981' },
  { key: 'denied', name: 'Denied', color: '#ef4444' },
]

export function RevenueTrendChart({ data }) {
  if (data.length === 0) return <Empty />
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 5, right: 10, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={GRID_STROKE} vertical={false} />
        <XAxis dataKey="month" tickFormatter={monthLabel} tick={AXIS_TICK} minTickGap={16} />
        <YAxis tickFormatter={compactCurrency} tick={AXIS_TICK} width={64} />
        <Tooltip
          labelFormatter={monthLabel}
          formatter={(value, name) => [currency.format(value), name]}
        />
        <Legend iconType="plainline" wrapperStyle={{ fontSize: 12 }} />
        {REVENUE_SERIES.map(({ key, name, color }) => (
          <Line
            key={key}
            dataKey={key}
            name={name}
            stroke={color}
            strokeWidth={2}
            dot={data.length <= 12}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}

function DenialTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const reason = payload[0].payload
  return (
    <div className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs shadow-sm">
      <div className="font-semibold text-gray-900">{reason.category}</div>
      <div className="text-gray-700">{reason.denials.toLocaleString()} denials</div>
      <div className="text-gray-700">{currency.format(reason.amount)} denied</div>
      <div className="text-gray-500">
        {percent(reason.denials ? reason.preventable / reason.denials : 0, 0)} preventable
      </div>
    </div>
  )
}

export function DenialReasonsChart({ data }) {
  if (data.length === 0) return <Empty />
  return (
    <ResponsiveContainer width="100%" height={Math.max(160, data.length * 40)}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={GRID_STROKE} horizontal={false} />
        <XAxis type="number" tick={AXIS_TICK} allowDecimals={false} tickFormatter={count} />
        <YAxis type="category" dataKey="category" tick={AXIS_TICK} width={150} interval={0} />
        <Tooltip content={<DenialTooltip />} cursor={{ fill: '#f9fafb' }} />
        <Bar dataKey="denials" name="Denials" fill="#ef4444" radius={[0, 4, 4, 0]} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  )
}

function AgingTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const bucket = payload[0].payload
  return (
    <div className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs shadow-sm">
      <div className="font-semibold text-gray-900">{bucket.label} days</div>
      <div className="text-gray-700">{bucket.claims.toLocaleString()} claims</div>
      <div className="text-gray-500">{currency.format(bucket.charges)} billed</div>
    </div>
  )
}

// Older buckets get warmer colors
const AGING_COLORS = ['#10b981', '#f59e0b', '#f97316', '#ef4444']

export function ArAgingChart({ data }) {
  if (data.every((bucket) => bucket.claims === 0)) return <Empty />
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 5, right: 10, bottom: 12, left: 0 }}>
        <CartesianGrid stroke={GRID_STROKE} vertical={false} />
        <XAxis
          dataKey="label"
          tick={AXIS_TICK}
          interval={0}
          label={{ ...AXIS_TICK, value: 'Days in AR', position: 'insideBottom', offset: -2 }}
        />
        <YAxis tick={AXIS_TICK} allowDecimals={false} width={56} tickFormatter={count} />
        <Tooltip content={<AgingTooltip />} cursor={{ fill: '#f9fafb' }} />
        <Bar dataKey="claims" name="Claims" radius={[4, 4, 0, 0]} isAnimationActive={false}>
          {data.map((bucket, index) => (
            <Cell key={bucket.label} fill={AGING_COLORS[index % AGING_COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export function ClaimStatusChart({ data }) {
  const total = data.reduce((sum, row) => sum + row.claims, 0)
  if (total === 0) return <Empty />
  // Only plain data fields: Pie passes each entry's keys through to its SVG paths
  const rows = data.map((row) => {
    const { label, color } = VALIDATION_STATUSES[row.status]
    return { ...row, label, color }
  })
  return (
    <div className="flex flex-wrap items-center gap-4">
      <div className="h-48 w-48 shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={rows}
              dataKey="claims"
              nameKey="label"
              innerRadius="60%"
              outerRadius="100%"
              paddingAngle={1}
              isAnimationActive={false}
            >
              {rows.map((row) => (
                <Cell key={row.status} fill={row.color} />
              ))}
            </Pie>
            <Tooltip formatter={(value, name) => [value.toLocaleString(), name]} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="min-w-40 flex-1 space-y-2 text-sm">
        {rows.map((row) => (
          <li key={row.status} className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className="h-3 w-3 shrink-0 rounded-sm"
              style={{ backgroundColor: row.color }}
            />
            <span className="text-gray-700">{row.label}</span>
            <span className="ml-auto tabular-nums font-medium text-gray-900">
              {row.claims.toLocaleString()}
            </span>
            <span className="w-14 text-right tabular-nums text-gray-500">
              {percent(row.claims / total)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function PayerTable({ payers }) {
  if (payers.length === 0) return <Empty />
  return (
    <div className="relative overflow-x-auto">
      <table className="w-full whitespace-nowrap text-sm">
        <thead>
          <tr className="border-b border-gray-100 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
            <th scope="col" className="py-2 pr-4">Payer</th>
            <th scope="col" className="py-2 pr-4 text-right">Claims</th>
            <th scope="col" className="py-2 pr-4 text-right">Denial rate</th>
            <th scope="col" className="py-2 pr-4 text-right">Avg days in AR</th>
            <th scope="col" className="py-2 text-right">Collected</th>
          </tr>
        </thead>
        <tbody>
          {payers.map((payer) => (
            <tr key={payer.payer_id} className="border-b border-gray-50 last:border-0">
              <td className="py-2 pr-4 font-medium text-gray-900">{payer.payer_name}</td>
              <td className="py-2 pr-4 text-right tabular-nums text-gray-700">
                {payer.claims.toLocaleString()}
              </td>
              <td className="py-2 pr-4 text-right tabular-nums text-gray-700">
                {percent(payer.denial_rate)}
              </td>
              <td className="py-2 pr-4 text-right tabular-nums text-gray-700">
                {payer.avg_days_in_ar.toFixed(1)}
              </td>
              <td className="py-2 text-right tabular-nums text-gray-700">
                {compactCurrency(payer.paid)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
