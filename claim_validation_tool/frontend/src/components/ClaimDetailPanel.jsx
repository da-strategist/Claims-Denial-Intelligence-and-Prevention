import { useState } from 'react'
import { VALIDATION_STATUSES } from '../constants'
import { useClaimDetail, useClaimFixes } from '../hooks/useClaims'
import { applyFix, undoCorrections } from '../services/api'
import { currency } from '../utils/format'
import FixSuggestion from './FixSuggestion'
import { SeverityBadge, ValidationBadge } from './StatusBadge'

function Section({ title, children }) {
  return (
    <section className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">{title}</h3>
      {children}
    </section>
  )
}

function Findings({ validation, suggestions, onApply }) {
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
          {suggestions?.[finding.rule_id] && (
            <div className="mt-3">
              <FixSuggestion suggestion={suggestions[finding.rule_id]} onApply={onApply} />
            </div>
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

function Denials({ denials, suggestions, onApply }) {
  return (
    <ul className="space-y-2">
      {denials.map((denial) => (
        <li key={denial.denial_id} className="space-y-3">
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm">
            <div className="font-semibold text-red-900">{denial.denial_reason_text}</div>
            <div className="mt-1 text-red-800">
              {denial.denial_date} · CARC {denial.carc_code} / RARC {denial.rarc_code} ·{' '}
              {currency.format(denial.denial_amount)}
              {denial.is_preventable && ' · Preventable'}
            </div>
          </div>
          {suggestions?.[`appeal:${denial.denial_id}`] && (
            <FixSuggestion suggestion={suggestions[`appeal:${denial.denial_id}`]} onApply={onApply} />
          )}
        </li>
      ))}
    </ul>
  )
}

const FIELD_LABELS = {
  primary_icd10: 'Primary ICD-10',
  pa_obtained: 'Prior auth obtained',
  pa_number: 'Prior auth number',
  is_clean_claim: 'Clean claim',
}

function describeCorrection({ field, old_value, new_value }) {
  const show = (v) => (v === 'true' ? 'Yes' : v === 'false' ? 'No' : (v ?? '—'))
  return `${FIELD_LABELS[field] ?? field}: ${show(old_value)} → ${show(new_value)}`
}

function statusLabel(validation) {
  return `${VALIDATION_STATUSES[validation.status]?.label ?? validation.status} (risk ${validation.risk_score})`
}

/** Result of the last applied fix: what changed and the re-validated status. */
function ApplyResult({ result, onDismiss }) {
  const { before, after, applied } = result
  return (
    <div
      role="status"
      className="flex items-start justify-between gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900"
    >
      <div>
        <div className="font-semibold">
          Fix applied: {statusLabel(before)} → {statusLabel(after.validation)}
        </div>
        <div className="text-emerald-800">
          {applied.map(describeCorrection).join(' · ')}
        </div>
      </div>
      <button onClick={onDismiss} aria-label="Dismiss" className="text-emerald-700 hover:text-emerald-900">
        ✕
      </button>
    </div>
  )
}

function Corrections({ corrections, onUndo }) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const undo = async () => {
    setBusy(true)
    try {
      await onUndo()
    } finally {
      setBusy(false)
      setConfirming(false)
    }
  }
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3">
      <ul className="space-y-1 text-sm">
        {corrections.map((c) => (
          <li key={c.id} className="flex flex-wrap justify-between gap-x-3 text-gray-700">
            <span>{describeCorrection(c)}</span>
            <span className="text-xs text-gray-400">
              {c.id} · {new Date(c.applied_at).toLocaleString()}
            </span>
          </li>
        ))}
      </ul>
      <div className="mt-2 flex items-center gap-2 border-t border-gray-100 pt-2 text-sm">
        {confirming ? (
          <>
            <span className="text-gray-600">Restore the claim's original values?</span>
            <button
              onClick={undo}
              disabled={busy}
              className="rounded-lg bg-red-600 px-2.5 py-1 font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              Undo all
            </button>
            <button
              onClick={() => setConfirming(false)}
              className="rounded-lg px-2.5 py-1 text-gray-600 hover:bg-gray-100"
            >
              Cancel
            </button>
          </>
        ) : (
          <button
            onClick={() => setConfirming(true)}
            className="font-medium text-red-700 hover:text-red-800"
          >
            Undo corrections
          </button>
        )}
      </div>
    </div>
  )
}

/** Suggestions keyed by what they address: a rule ID, or `appeal:<denial_id>`. */
function suggestionsByTarget(fixes) {
  return Object.fromEntries(
    (fixes?.suggestions ?? []).map((s) => [s.id.slice(s.claim_id.length + 1), s]),
  )
}

/**
 * Expanded-row content: findings with AI Fix suggestions, risk breakdown, corrections,
 * and claim detail. `onClaimChanged` runs after a fix is applied or undone.
 */
export default function ClaimDetailPanel({ claim, validation: pageValidation, onClaimChanged }) {
  const { data: detail, loading, error } = useClaimDetail(claim.claim_id)
  const fixes = useClaimFixes(claim.claim_id)
  const [result, setResult] = useState(null)
  const [undoError, setUndoError] = useState(null)

  const validation = fixes.data?.validation ?? pageValidation
  const suggestions = suggestionsByTarget(fixes.data)

  const handleApply = async (suggestion, values) => {
    const applied = await applyFix(claim.claim_id, suggestion.id, values)
    setResult(applied)
    fixes.reload()
    onClaimChanged?.()
  }

  const handleUndo = async () => {
    setUndoError(null)
    try {
      await undoCorrections(claim.claim_id)
      setResult(null)
      fixes.reload()
      onClaimChanged?.()
    } catch (err) {
      setUndoError(err.message)
    }
  }

  return (
    <div className="grid gap-6 whitespace-normal bg-gray-50 px-6 py-5 lg:grid-cols-2">
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
          {result && <ApplyResult result={result} onDismiss={() => setResult(null)} />}
          {fixes.error && (
            <p className="text-sm text-amber-700">Could not load suggested fixes — {fixes.error}</p>
          )}
          <Findings validation={validation} suggestions={suggestions} onApply={handleApply} />
        </Section>
        <Section title="Risk breakdown">
          <RiskBreakdown validation={validation} />
        </Section>
        {fixes.data?.corrections.length > 0 && (
          <Section title="Corrections applied">
            <Corrections corrections={fixes.data.corrections} onUndo={handleUndo} />
            {undoError && <p className="text-sm text-red-700">Could not undo — {undoError}</p>}
          </Section>
        )}
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
            <Denials denials={detail.denials} suggestions={suggestions} onApply={handleApply} />
          </Section>
        )}
      </div>
    </div>
  )
}
