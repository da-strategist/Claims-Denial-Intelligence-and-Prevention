import { useId } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { VALIDATION_STATUSES } from '../constants'
import { compactCurrency, currency, monthLabel, percent } from '../utils/format'

const AXIS_TICK = { fontSize: 12, fill: '#8e8e93' }
const AXIS = { tick: AXIS_TICK, axisLine: false, tickLine: false }
const count = (value) => value.toLocaleString()
const GRID_STROKE = '#f0f0f3'
const QUIET = '#d1d1d7'
const LOSS = '#e5484d'
const CURSOR = { fill: '#f7f7f9' }
const TOOLTIP_CLASS = 'rounded-xl bg-white/95 px-3 py-2 text-xs shadow-lg ring-1 ring-gray-200/70 backdrop-blur'

/** Titled card for one chart. */
export function ChartCard({ title, subtitle, children, className = '' }) {
  const titleId = useId()
  return (
    <section
      aria-labelledby={titleId}
      className={`card min-w-0 p-5 sm:p-6 ${className}`}
    >
      <h2 id={titleId} className="text-[15px] font-semibold text-gray-900">
        {title}
      </h2>
      {subtitle && <p className="text-[13px] text-gray-500">{subtitle}</p>}
      <div className="mt-5">{children}</div>
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
  { key: 'charges', name: 'Billed', color: QUIET },
  { key: 'paid', name: 'Collected', color: '#0a6ce0' },
  { key: 'denied', name: 'Denied', color: LOSS },
]

function SeriesKey() {
  return (
    <ul className="mb-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-gray-500">
      {REVENUE_SERIES.map(({ key, name, color }) => (
        <li key={key} className="flex items-center gap-1.5">
          <span aria-hidden="true" className="h-0.5 w-3 rounded-full" style={{ backgroundColor: color }} />
          {name}
        </li>
      ))}
    </ul>
  )
}

export function RevenueTrendChart({ data }) {
  if (data.length === 0) return <Empty />
  return (
    <>
      <SeriesKey />
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 5, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={GRID_STROKE} vertical={false} />
          <XAxis dataKey="month" tickFormatter={monthLabel} minTickGap={16} {...AXIS} />
          <YAxis tickFormatter={compactCurrency} width={56} {...AXIS} />
          <Tooltip
            labelFormatter={monthLabel}
            formatter={(value, name) => [currency.format(value), name]}
            contentStyle={{ borderRadius: 12, border: '1px solid #e3e3e8', fontSize: 12 }}
          />
          {REVENUE_SERIES.map(({ key, name, color }) => (
            <Line
              key={key}
              dataKey={key}
              name={name}
              stroke={color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </>
  )
}

function DenialTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const reason = payload[0].payload
  return (
    <div className={TOOLTIP_CLASS}>
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
    <ResponsiveContainer width="100%" height={Math.max(160, data.length * 38)}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 0 }}>
        <XAxis type="number" hide allowDecimals={false} />
        <YAxis type="category" dataKey="category" width={150} interval={0} {...AXIS} />
        <Tooltip content={<DenialTooltip />} cursor={CURSOR} />
        {/* The biggest cause is the one to fix first */}
        <Bar dataKey="denials" name="Denials" barSize={18} radius={6} isAnimationActive={false}>
          {data.map((reason, index) => (
            <Cell key={reason.category} fill={index === 0 ? LOSS : QUIET} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function AgingTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const bucket = payload[0].payload
  return (
    <div className={TOOLTIP_CLASS}>
      <div className="font-semibold text-gray-900">{bucket.label} days</div>
      <div className="text-gray-700">{bucket.claims.toLocaleString()} claims</div>
      <div className="text-gray-500">{currency.format(bucket.charges)} billed</div>
    </div>
  )
}

// Only the buckets that are getting late get colour
const AGING_COLORS = [QUIET, '#a3a3ab', '#f5a623', LOSS]

export function ArAgingChart({ data }) {
  if (data.every((bucket) => bucket.claims === 0)) return <Empty />
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 5, right: 10, bottom: 12, left: 0 }}>
        <CartesianGrid stroke={GRID_STROKE} vertical={false} />
        <XAxis
          dataKey="label"
          interval={0}
          label={{ ...AXIS_TICK, value: 'Days in AR', position: 'insideBottom', offset: -2 }}
          {...AXIS}
        />
        <YAxis allowDecimals={false} width={56} tickFormatter={count} {...AXIS} />
        <Tooltip content={<AgingTooltip />} cursor={CURSOR} />
        <Bar dataKey="claims" name="Claims" barSize={56} radius={[6, 6, 0, 0]} isAnimationActive={false}>
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
  const rows = data.map((row) => ({ ...row, ...VALIDATION_STATUSES[row.status] }))
  return (
    <div className="space-y-6">
      <div
        aria-hidden="true"
        className="flex h-3 w-full gap-0.5 overflow-hidden rounded-full bg-gray-100"
      >
        {rows.map((row) => (
          <div
            key={row.status}
            className="h-full first:rounded-l-full last:rounded-r-full"
            style={{ width: `${(row.claims / total) * 100}%`, backgroundColor: row.color }}
          />
        ))}
      </div>
      <ul className="divide-y divide-gray-100 text-sm">
        {rows.map((row) => (
          <li key={row.status} className="flex items-center gap-3 py-2.5">
            <span aria-hidden="true" className={`h-2 w-2 shrink-0 rounded-full ${row.dot}`} />
            <span className="text-gray-700">{row.label}</span>
            <span className="ml-auto tabular-nums font-medium text-gray-900">
              {row.claims.toLocaleString()}
            </span>
            <span className="w-12 text-right tabular-nums text-gray-400">
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
          <tr className="border-b border-gray-100 text-left text-xs font-medium text-gray-500">
            <th scope="col" className="py-2 pr-4">Payer</th>
            <th scope="col" className="py-2 pr-4 text-right">Claims</th>
            <th scope="col" className="py-2 pr-4 text-right">Denial rate</th>
            <th scope="col" className="py-2 pr-4 text-right">Avg days in AR</th>
            <th scope="col" className="py-2 text-right">Collected</th>
          </tr>
        </thead>
        <tbody>
          {payers.map((payer) => (
            <tr key={payer.payer_id} className="border-b border-gray-100 last:border-0">
              <td className="py-2.5 pr-4 font-medium text-gray-900">{payer.payer_name}</td>
              <td className="py-2.5 pr-4 text-right tabular-nums text-gray-600">
                {payer.claims.toLocaleString()}
              </td>
              <td className="py-2.5 pr-4 text-right tabular-nums text-gray-600">
                {percent(payer.denial_rate)}
              </td>
              <td className="py-2.5 pr-4 text-right tabular-nums text-gray-600">
                {payer.avg_days_in_ar.toFixed(1)}
              </td>
              <td className="py-2.5 text-right tabular-nums text-gray-900">
                {compactCurrency(payer.paid)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
