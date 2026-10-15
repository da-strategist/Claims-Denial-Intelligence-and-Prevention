import { useClaimDetail } from '../hooks/useClaims'
import { currency } from '../utils/format'
import { SeverityBadge, ValidationBadge } from './StatusBadge'

function Section({ title, children }) {
  return (
    <section className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">{title}</h3>
      {children}
    </section>
  )
}

function Findings({ validation }) {
  if (!validation) return <p className="text-sm text-gray-500">Validating…</p>
  if (validation.findings.length === 0) {
    return <p className="text-sm text-emerald-700">All enabled rules passed.</p>
  }
  return (
    <ul className="space-y-2">
      {validation.findings.map((finding) => (
        <li key={finding.rule_id} className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={finding.severity} />
            <span className="text-sm font-semibold text-gray-900">{finding.rule_name}</span>
            <span className="text-xs text-gray-400">
              {finding.rule_id} · {finding.category}
            </span>
          </div>
          {finding.message && <p className="mt-1.5 text-sm text-gray-600">{finding.message}</p>}
          {finding.recommended_action && (
            <p className="mt-1.5 text-sm text-gray-800">
              <span className="font-medium">Recommended: </span>
              {finding.recommended_action}
            </p>
          )}
        </li>
      ))}
    </ul>
  )
}

function RiskBreakdown({ validation }) {
  if (!validation) return null
  const total = validation.risk_factors.reduce((sum, factor) => sum + factor.points, 0)
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3">
      {validation.risk_factors.length === 0 ? (
        <p className="text-sm text-gray-500">No risk factors.</p>
      ) : (
        <table className="w-full text-sm">
          <tbody>
            {validation.risk_factors.map((factor) => (
              <tr key={factor.label}>
                <td className="py-0.5 text-gray-600">{factor.label}</td>
                <td className="py-0.5 text-right tabular-nums text-gray-900">+{factor.points}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="mt-2 flex items-center justify-between border-t border-gray-100 pt-2 text-sm">
        <span className="font-semibold text-gray-900">Risk score</span>
        <span className="font-semibold tabular-nums text-gray-900">
          {validation.risk_score}
          {total > 100 && <span className="ml-1 font-normal text-gray-400">(capped at 100)</span>}
        </span>
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div>
      <dt className="text-xs text-gray-500">{label}</dt>
      <dd className="text-sm text-gray-900">{children ?? '—'}</dd>
    </div>
  )
}

function ClaimFacts({ claim, detail }) {
  const paLabel = claim.pa_required
    ? claim.pa_obtained
      ? `Obtained${claim.pa_number ? ` (${claim.pa_number})` : ''}`
      : 'Required — not obtained'
    : 'Not required'
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg border border-gray-200 bg-white p-3">
      <Field label="Provider">
        {detail?.provider
          ? `${detail.provider.provider_name}, ${detail.provider.credential}`
          : claim.provider_id}
      </Field>
      <Field label="Specialty">{detail?.provider?.specialty}</Field>
      <Field label="Primary ICD-10">{claim.primary_icd10}</Field>
      <Field label="Place of service">{claim.place_of_service}</Field>
      <Field label="Submitted">{claim.submission_date}</Field>
      <Field label="Prior auth">{paLabel}</Field>
      <Field label="Allowed">{currency.format(claim.total_allowed)}</Field>
      <Field label="Patient responsibility">{currency.format(claim.patient_responsibility)}</Field>
    </dl>
  )
}

function ClaimLines({ lines }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100 text-left text-xs text-gray-500">
            <th className="px-3 py-2 font-medium">#</th>
            <th className="px-3 py-2 font-medium">CPT</th>
            <th className="px-3 py-2 font-medium">Modifier</th>
            <th className="px-3 py-2 font-medium">ICD-10</th>
            <th className="px-3 py-2 text-right font-medium">Units</th>
            <th className="px-3 py-2 text-right font-medium">Charge</th>
            <th className="px-3 py-2 text-right font-medium">Paid</th>
          </tr>
        </thead>
        <tbody>
          {lines.map((line) => (
            <tr key={line.line_id} className="border-b border-gray-50 last:border-0">
              <td className="px-3 py-1.5 text-gray-500">{line.line_number}</td>
              <td className="px-3 py-1.5 text-gray-900">
                {line.cpt_code} <span className="text-gray-400">{line.cpt_category}</span>
              </td>
              <td className="px-3 py-1.5 text-gray-600">{line.modifier ?? '—'}</td>
              <td className="px-3 py-1.5 text-gray-600">{line.icd10_pointer}</td>
              <td className="px-3 py-1.5 text-right tabular-nums text-gray-600">{line.units}</td>
              <td className="px-3 py-1.5 text-right tabular-nums text-gray-900">
                {currency.format(line.charge_amount)}
              </td>
              <td className="px-3 py-1.5 text-right tabular-nums text-gray-600">
                {currency.format(line.paid_amount)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Denials({ denials }) {
  return (
    <ul className="space-y-2">
      {denials.map((denial) => (
        <li key={denial.denial_id} className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm">
          <div className="font-semibold text-red-900">{denial.denial_reason_text}</div>
          <div className="mt-1 text-red-800">
            {denial.denial_date} · CARC {denial.carc_code} / RARC {denial.rarc_code} ·{' '}
            {currency.format(denial.denial_amount)}
            {denial.is_preventable && ' · Preventable'}
          </div>
        </li>
      ))}
    </ul>
  )
}

/** Expanded-row content: validation findings, risk breakdown, and claim detail. */
export default function ClaimDetailPanel({ claim, validation }) {
  const { data: detail, loading, error } = useClaimDetail(claim.claim_id)

  return (
    <div className="grid gap-6 bg-gray-50 px-6 py-5 lg:grid-cols-2">
      <div className="space-y-5">
        <Section title="Validation">
          <div className="flex items-center gap-2">
            <ValidationBadge status={validation?.status} />
            {validation && (
              <span className="text-sm text-gray-500">
                {validation.findings.length} finding{validation.findings.length === 1 ? '' : 's'}
              </span>
            )}
          </div>
          <Findings validation={validation} />
        </Section>
        <Section title="Risk breakdown">
          <RiskBreakdown validation={validation} />
        </Section>
      </div>

      <div className="space-y-5">
        <Section title="Claim detail">
          <ClaimFacts claim={claim} detail={detail} />
        </Section>
        {error && <p className="text-sm text-red-700">Could not load claim detail — {error}</p>}
        {loading && !detail && <p className="text-sm text-gray-500">Loading claim lines…</p>}
        {detail && (
          <Section title={`Claim lines (${detail.lines.length})`}>
            <ClaimLines lines={detail.lines} />
          </Section>
        )}
        {detail?.denials.length > 0 && (
          <Section title="Payer denial">
            <Denials denials={detail.denials} />
          </Section>
        )}
      </div>
    </div>
  )
}
