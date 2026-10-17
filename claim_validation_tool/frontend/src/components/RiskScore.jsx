// Same cut-offs the backend uses: 60+ with an error routes a claim to AI Fix
function riskLevel(score) {
  if (score >= 60) return { label: 'High', bar: 'bg-red-500', text: 'text-red-700 font-semibold' }
  if (score >= 30) return { label: 'Medium', bar: 'bg-amber-500', text: 'text-amber-700' }
  return { label: 'Low', bar: 'bg-emerald-500', text: 'text-emerald-700' }
}

/** Compact 0-100 risk score with a bar, for table cells: green low, amber medium, red high. */
export default function RiskScore({ score }) {
  if (score === undefined || score === null) {
    return <span className="text-sm text-gray-300">—</span>
  }
  const level = riskLevel(score)
  return (
    <div className="flex items-center justify-end gap-2" title={`${level.label} risk`}>
      <div className="hidden h-1 w-10 overflow-hidden rounded-full bg-gray-100 lg:block">
        <div className={`h-full rounded-full ${level.bar}`} style={{ width: `${score}%` }} />
      </div>
      <span className={`w-7 text-right text-sm tabular-nums ${level.text}`}>{score}</span>
    </div>
  )
}
