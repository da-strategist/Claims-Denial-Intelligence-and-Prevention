import { useState } from 'react'
import { VALIDATION_STATUSES } from '../constants'
import { useClaimDetail, useClaimFixes, usePayerLookup } from '../hooks/useClaims'
import { applyFix, undoCorrections } from '../services/api'
import { useCan } from '../hooks/useAuth'
import SubmitClaim from './SubmitClaim'
import { currency } from '../utils/format'
import EdiFileCard from './EdiFileCard'
import FixSuggestion from './FixSuggestion'
import Icon from './Icon'
import { SeverityBadge } from './StatusBadge'

function Section({ title, children }) {
  return (
    <section className="space-y-2">
      <h3 className="eyebrow">{title}</h3>
      {children}
    </section>
  )
}

function Findings({ validation, suggestions, onApply }) {
  if (!validation) return <p className="text-sm text-gray-500">Validating…</p>
  if (validation.findings.length === 0) {
    return (
      <p className="flex items-center gap-2 text-sm text-gray-700">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
          <Icon name="check" className="h-3.5 w-3.5" strokeWidth={2.25} />
        </span>
        All enabled rules passed.
      </p>
    )
  }
  return (
    <ul className="divide-y divide-gray-100">
      {validation.findings.map((finding) => (
        <li key={finding.rule_id} className="py-4 first:pt-1 last:pb-0">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={finding.severity} />
            <span className="text-[15px] font-semibold text-gray-900">{finding.rule_name}</span>
            <span className="text-xs text-gray-400">
              {finding.rule_id} · {finding.category}
            </span>
          </div>
          {finding.message && <p className="mt-1.5 text-sm text-gray-600">{finding.message}</p>}
          {finding.recommended_action && !suggestions?.[finding.rule_id] && (
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
    <div>
      {validation.risk_factors.length === 0 ? (
        <p className="text-sm text-gray-500">No risk factors.</p>
      ) : (
        <table className="w-full text-sm">
          <tbody>
            {validation.risk_factors.map((factor) => (
              <tr key={factor.label}>
                <td className="py-1 text-gray-600">{factor.label}</td>
                <td className="py-1 text-right tabular-nums text-gray-500">+{factor.points}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="mt-2 flex items-center justify-between border-t border-gray-200 pt-2 text-sm">
        <span className="font-semibold text-gray-900">Risk score</span>
        <span className="font-semibold tabular-nums text-gray-900">
          {validation.risk_score}
          {total > 100 && <span className="ml-1 font-normal text-gray-400">(capped at 100)</span>}
        </span>
      </div>
    </div>
  )
}

function Field({ label, children, className = '' }) {
  return (
    <div className={className}>
      <dt className="text-xs text-gray-400">{label}</dt>
      <dd className="text-sm text-gray-900">{children ?? '—'}</dd>
    </div>
  )
}

function ClaimFacts({ claim, detail, payers }) {
  const paLabel = claim.pa_required
    ? claim.pa_obtained
      ? `Obtained${claim.pa_number ? ` (${claim.pa_number})` : ''}`
      : 'Required — not obtained'
    : 'Not required'
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-3">
      <Field label="Patient">
        {detail?.patient
          ? `${detail.patient.first_name} ${detail.patient.last_name} · ${detail.patient.age} ${detail.patient.gender}`
          : claim.patient_id}
      </Field>
      <Field label="Patient ID">{claim.patient_id}</Field>
      {detail?.billing && (
        <>
          <Field label="Date of birth">{detail.billing.patient_birth_date}</Field>
          <Field label="Member ID">{detail.billing.policy?.member_id ?? 'Self-pay'}</Field>
        </>
      )}
      {/* Columns the workbench table hides on narrow screens */}
      <Field label="Service date" className="sm:hidden">
        {claim.service_date}
      </Field>
      <Field label="Charge" className="sm:hidden">
        {currency.format(claim.total_charge)}
      </Field>
      <Field label="Payer" className="lg:hidden">
        {payers?.[claim.payer_id]?.payer_name ?? claim.payer_id}
      </Field>
      <Field label="Claim type" className="2xl:hidden">
        {claim.claim_type}
      </Field>
      <Field label="Provider">
        {detail?.provider
          ? `${detail.provider.provider_name}, ${detail.provider.credential}`
          : claim.provider_id}
      </Field>
      <Field label="Specialty">{detail?.provider?.specialty}</Field>
      <Field label="Primary ICD-10">{claim.primary_icd10}</Field>
      {claim.additional_icd10?.length > 0 && (
        <Field label="Other diagnoses">{claim.additional_icd10.join(', ')}</Field>
      )}
      {claim.other_payer_ids?.length > 0 && (
        <Field label="Other coverage">
          {claim.other_payer_ids.map((id) => payers?.[id]?.payer_name ?? id).join(' → ')}
        </Field>
      )}
      <Field label="Place of service">{claim.place_of_service}</Field>
      <Field label="Submitted">{claim.submission_date}</Field>
      <Field label="Prior auth">{paLabel}</Field>
      <Field label="Allowed">{currency.format(claim.total_allowed)}</Field>
      <Field label="Paid" className="2xl:hidden">
        {currency.format(claim.total_paid)}
      </Field>
      <Field label="Days in AR" className="lg:hidden">
        {claim.days_in_ar}
      </Field>
      <Field label="Patient responsibility">{currency.format(claim.patient_responsibility)}</Field>
    </dl>
  )
}

function ClaimLines({ lines }) {
  const head = 'px-3 py-2 font-medium'
  const cell = 'px-3 py-2'
  return (
    <div className="overflow-x-auto rounded-xl ring-1 ring-gray-200/70">
      <table className="w-full whitespace-nowrap text-[13px]">
        <thead>
          <tr className="border-b border-gray-100 text-left text-xs text-gray-500">
            <th className={head}>CPT</th>
            <th className={head}>Mod</th>
            <th className={head}>ICD-10</th>
            <th className={`${head} text-right`}>Units</th>
            <th className={`${head} text-right`}>Charge</th>
            <th className={`${head} text-right`}>Paid</th>
          </tr>
        </thead>
        <tbody>
          {lines.map((line) => (
            <tr key={line.line_id} className="border-b border-gray-100 last:border-0">
              <td className={`${cell} text-gray-900`} title={line.cpt_category}>
                {line.cpt_code}
              </td>
              <td className={`${cell} text-gray-600`}>{line.modifier ?? '—'}</td>
              <td className={`${cell} text-gray-600`}>{line.icd10_pointer}</td>
              <td className={`${cell} text-right text-gray-600`}>{line.units}</td>
              <td className={`${cell} text-right text-gray-900`}>{currency.format(line.charge_amount)}</td>
              <td className={`${cell} text-right text-gray-600`}>{currency.format(line.paid_amount)}</td>
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
          <div className="rounded-2xl bg-red-50 p-4 text-sm">
            <div className="font-semibold text-red-900">{denial.denial_reason_text}</div>
            <div className="mt-1 text-red-800/80">
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
      className="flex items-start justify-between gap-3 rounded-2xl bg-emerald-50 p-4 text-sm text-emerald-900"
    >
      <div>
        <div className="font-semibold">
          Fix applied: {statusLabel(before)} → {statusLabel(after.validation)}
        </div>
        <div className="text-emerald-800">
          {applied.map(describeCorrection).join(' · ')}
        </div>
      </div>
      <button
        onClick={onDismiss}
        aria-label="Dismiss"
        className="rounded-lg p-1 text-emerald-700 hover:bg-emerald-100 hover:text-emerald-900"
      >
        <Icon name="close" className="h-4 w-4" />
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
    <div>
      <ul className="space-y-1 text-sm">
        {corrections.map((c) => (
          <li key={c.id} className="flex flex-wrap justify-between gap-x-3 text-gray-700">
            <span>{describeCorrection(c)}</span>
            <span className="text-xs text-gray-400">
              {c.id} · {new Date(c.applied_at).toLocaleString()}
              {c.applied_by && ` · ${c.applied_by}`}
            </span>
          </li>
        ))}
      </ul>
      {onUndo && (
        <div className="mt-2 flex items-center gap-2 border-t border-gray-100 pt-2 text-sm">
          {confirming ? (
            <>
              <span className="text-gray-600">Restore the claim's original values?</span>
              <button onClick={undo} disabled={busy} className="btn-danger btn-sm">
                Undo all
              </button>
              <button onClick={() => setConfirming(false)} className="btn-secondary btn-sm">
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
      )}
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
 * and claim detail. `onClaimChanged` runs after a fix is applied or undone, or the claim is
 * submitted. `stacked` lays it out in one column, for narrow spaces.
 */
export default function ClaimDetailPanel({
  claim,
  validation: pageValidation,
  onClaimChanged,
  stacked = false,
}) {
  const { data: detail, loading, error } = useClaimDetail(claim.claim_id)
  const fixes = useClaimFixes(claim.claim_id)
  const payers = usePayerLookup()
  const [result, setResult] = useState(null)
  const [undoError, setUndoError] = useState(null)
  // Roles without claims:write see the suggestions but can't apply, undo, or submit
  const canEdit = useCan('claims:write')

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

  const findingCount = validation?.findings.length ?? 0

  return (
    <div
      className={
        stacked
          ? 'grid grid-cols-1 gap-8'
          : 'grid grid-cols-1 gap-8 whitespace-normal border-t border-gray-100 bg-white px-4 py-6 sm:px-8 lg:grid-cols-5'
      }
    >
      <div className={stacked ? 'space-y-6' : 'space-y-6 lg:col-span-3'}>
        <Section
          title={
            findingCount
              ? `${findingCount} ${findingCount === 1 ? 'problem' : 'problems'} to resolve`
              : 'Validation'
          }
        >
          {result && <ApplyResult result={result} onDismiss={() => setResult(null)} />}
          {fixes.error && (
            <p className="text-sm text-amber-700">Could not load suggested fixes — {fixes.error}</p>
          )}
          <Findings
            validation={validation}
            suggestions={suggestions}
            onApply={canEdit ? handleApply : null}
          />
          {/* Last: fix the problems above, then submit */}
          {canEdit && (
            <SubmitClaim
              claim={claim}
              validation={validation}
              onSubmitted={() => {
                fixes.reload()
                onClaimChanged?.()
              }}
            />
          )}
        </Section>
        {fixes.data?.corrections.length > 0 && (
          <Section title="Corrections applied">
            <Corrections
              corrections={fixes.data.corrections}
              onUndo={canEdit ? handleUndo : null}
            />
            {undoError && <p className="text-sm text-red-700">Could not undo — {undoError}</p>}
          </Section>
        )}
      </div>

      <div
        className={
          stacked
            ? 'space-y-6 border-t border-gray-100 pt-8'
            : 'space-y-6 lg:col-span-2 lg:border-l lg:border-gray-100 lg:pl-8'
        }
      >
        {detail?.edi && (
          <Section title="Submitted as">
            <EdiFileCard claimId={claim.claim_id} edi={detail.edi} />
          </Section>
        )}
        {detail?.denials.length > 0 && (
          <Section title="Payer denial">
            <Denials
              denials={detail.denials}
              suggestions={suggestions}
              onApply={canEdit ? handleApply : null}
            />
          </Section>
        )}
        <Section title="Claim">
          <ClaimFacts claim={claim} detail={detail} payers={payers} />
        </Section>
        {error && <p className="text-sm text-red-700">Could not load claim detail — {error}</p>}
        {loading && !detail && <p className="text-sm text-gray-500">Loading claim lines…</p>}
        {detail && (
          <Section title={`Lines (${detail.lines.length})`}>
            <ClaimLines lines={detail.lines} />
          </Section>
        )}
        <Section title="Why the risk score">
          <RiskBreakdown validation={validation} />
        </Section>
      </div>
    </div>
  )
}
