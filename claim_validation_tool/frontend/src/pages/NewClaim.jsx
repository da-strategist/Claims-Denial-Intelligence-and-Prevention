import { useId, useState } from 'react'
import {
  CoverageFields,
  DiagnosisList,
  FormSection,
  PatientPicker,
  ServiceLines,
} from '../components/ClaimEntryFields'
import RiskScore from '../components/RiskScore'
import { ClaimStatusBadge, SeverityBadge, ValidationBadge } from '../components/StatusBadge'
import SubmitClaim from '../components/SubmitClaim'
import Toggle from '../components/Toggle'
import { CLAIM_TYPES, INPUT_CLASS, PLACES_OF_SERVICE } from '../constants'
import { useClaimEntryLists } from '../hooks/useClaimEntry'
import { usePayerLookup } from '../hooks/useClaims'
import { useDepartmentLookup } from '../hooks/useRules'
import { createClaim } from '../services/api'
import { lineCharge, unsupportedDiagnoses } from '../utils/claimEntry'
import { currency } from '../utils/format'
import { routeHref } from '../utils/route'

const DEFAULT_FACILITY = 'FAC001'

/** Today as YYYY-MM-DD in local time (toISOString would give the UTC date). */
function today() {
  const now = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

let nextLineKey = 1
const emptyLine = (dx = 0) => ({ key: nextLineKey++, cpt_code: '', units: '1', modifier: '', charge: '', dx })

const emptyForm = () => ({
  patient: null,
  payer_id: '',
  other_payer_ids: [],
  provider_id: '',
  facility_id: DEFAULT_FACILITY,
  diagnoses: [''],
  lines: [emptyLine()],
  claim_type: 'Professional',
  place_of_service: '11',
  service_date: '',
  submission_date: today(),
  pa_required: false,
  pa_obtained: false,
  pa_number: '',
})

/** Request body. Lines point at diagnoses by position in the form; send the codes. */
function toRequest(form, procedures) {
  const paObtained = form.pa_required && form.pa_obtained
  return {
    patient_id: form.patient.patient_id,
    payer_id: form.payer_id,
    other_payer_ids: form.other_payer_ids,
    provider_id: form.provider_id,
    facility_id: form.facility_id,
    diagnoses: form.diagnoses.map((code) => code.trim().toUpperCase()),
    lines: form.lines.map((line) => ({
      cpt_code: line.cpt_code,
      units: Number(line.units),
      modifier: line.modifier.trim() || null,
      charge_amount: line.charge === '' ? null : lineCharge(line, procedures),
      icd10_pointer: form.diagnoses[line.dx].trim().toUpperCase(),
    })),
    claim_type: form.claim_type,
    place_of_service: form.place_of_service,
    service_date: form.service_date,
    submission_date: form.submission_date,
    pa_required: form.pa_required,
    pa_obtained: paObtained,
    pa_number: paObtained && form.pa_number.trim() ? form.pa_number.trim() : null,
  }
}

function Field({ label, htmlFor, hint, children }) {
  return (
    <div className="space-y-1">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-gray-800">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-gray-500">{hint}</p>}
    </div>
  )
}

function ToggleField({ label, checked, onChange }) {
  return (
    <div className="flex items-center gap-3">
      <Toggle checked={checked} onChange={onChange} label={label} />
      <span className="text-sm text-gray-800">{label}</span>
      <span className="text-sm text-gray-500">{checked ? 'Yes' : 'No'}</span>
    </div>
  )
}

/** Providers grouped by department; the claim's department follows the provider. */
function ProviderSelect({ id, providers, departments, value, onChange }) {
  const groups = {}
  for (const provider of Object.values(providers)) {
    if (provider.status !== 'Active') continue
    ;(groups[provider.department_id] ??= []).push(provider)
  }
  const name = (deptId) => departments[deptId]?.department_name ?? deptId
  return (
    <select id={id} required className={INPUT_CLASS} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">Select a provider…</option>
      {Object.keys(groups)
        .sort((a, b) => name(a).localeCompare(name(b)))
        .map((deptId) => (
          <optgroup key={deptId} label={name(deptId)}>
            {groups[deptId]
              .sort((a, b) => a.provider_name.localeCompare(b.provider_name))
              .map((provider) => (
                <option key={provider.provider_id} value={provider.provider_id}>
                  {provider.provider_name}, {provider.credential} — {provider.specialty}
                </option>
              ))}
          </optgroup>
        ))}
    </select>
  )
}

function ValidationResult({ result, onReset, onSubmitted }) {
  const { claim, validation } = result
  return (
    <section
      aria-labelledby="new-claim-result"
      className="max-w-3xl space-y-4 rounded-xl border border-gray-100 bg-white p-5 shadow-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="new-claim-result" className="text-lg font-semibold text-gray-900">
            Created {claim.claim_id}
          </h2>
          <p className="text-sm text-gray-500">
            {claim.patient
              ? `${claim.patient.first_name} ${claim.patient.last_name} (${claim.patient_id})`
              : claim.patient_id}{' '}
            · {claim.payer?.payer_name ?? claim.payer_id} · {claim.lines.length} line
            {claim.lines.length === 1 ? '' : 's'} · {currency.format(claim.total_charge)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <a
            href={routeHref('#/claims', { search: claim.claim_id })}
            className="rounded-lg bg-red-600 px-3 py-2 text-sm font-semibold text-white hover:bg-red-700"
          >
            View in Workbench
          </a>
          <button
            type="button"
            onClick={onReset}
            className="rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Enter another claim
          </button>
        </div>
      </div>

      <SubmitClaim claim={claim} validation={validation} onSubmitted={onSubmitted} />

      <div className="flex flex-wrap items-center gap-6">
        <div className="space-y-1">
          <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Status</div>
          <ClaimStatusBadge status={claim.status} overdue={claim.is_overdue} />
        </div>
        <div className="space-y-1">
          <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Validation</div>
          <ValidationBadge status={validation.status} />
        </div>
        <div className="space-y-1">
          <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Risk score</div>
          <RiskScore score={validation.risk_score} />
        </div>
      </div>

      {validation.risk_factors.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-800">Risk factors</h3>
          <ul className="mt-1 space-y-0.5 text-sm text-gray-700">
            {validation.risk_factors.map((factor) => (
              <li key={factor.label} className="flex justify-between gap-4 sm:max-w-sm">
                <span>{factor.label}</span>
                <span className="tabular-nums text-gray-500">+{factor.points}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <h3 className="text-sm font-semibold text-gray-800">Findings</h3>
        {validation.findings.length === 0 ? (
          <p className="mt-1 text-sm text-emerald-700">No rules flagged this claim.</p>
        ) : (
          <ul className="mt-2 space-y-2">
            {validation.findings.map((finding) => (
              <li key={finding.rule_id} className="rounded-lg border border-gray-100 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <SeverityBadge severity={finding.severity} />
                  <span className="text-sm font-semibold text-gray-900">{finding.rule_name}</span>
                  <span className="text-xs text-gray-400">{finding.rule_id}</span>
                </div>
                {finding.message && <p className="mt-1 text-sm text-gray-700">{finding.message}</p>}
                {finding.recommended_action && (
                  <p className="mt-1 text-sm text-gray-500">→ {finding.recommended_action}</p>
                )}
              </li>
            ))}
          </ul>
        )}
        {validation.status === 'aifix' && (
          <p className="mt-2 text-sm text-violet-700">
            ✦ Open it in the workbench to review the suggested fixes.
          </p>
        )}
      </div>
    </section>
  )
}


export default function NewClaim() {
  const formId = useId()
  const id = (name) => `${formId}-${name}`
  const payers = usePayerLookup()
  const departments = useDepartmentLookup()
  const lists = useClaimEntryLists()
  const [form, setForm] = useState(emptyForm)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  const change = (changes) => setForm((prev) => ({ ...prev, ...changes }))

  // A new patient brings their registered primary payer as the default billed payer
  const choosePatient = (patient) =>
    change({ patient, payer_id: patient?.primary_payer_id ?? '', other_payer_ids: [] })

  // Lines point at diagnoses by position: removing one re-points the lines after it
  const removeDiagnosis = (index) =>
    setForm((prev) => ({
      ...prev,
      diagnoses: prev.diagnoses.filter((_, i) => i !== index),
      lines: prev.lines.map((line) => ({
        ...line,
        dx: line.dx === index ? 0 : line.dx > index ? line.dx - 1 : line.dx,
      })),
    }))

  // A new diagnosis gets a new line pointing at it, so it can't be left unsupported by accident
  const changeDiagnoses = (diagnoses) =>
    setForm((prev) =>
      diagnoses.length > prev.diagnoses.length
        ? { ...prev, diagnoses, lines: [...prev.lines, emptyLine(diagnoses.length - 1)] }
        : { ...prev, diagnoses },
    )

  const unsupported = unsupportedDiagnoses(form.diagnoses, form.lines)
  const provider = lists.providers[form.provider_id]

  const submit = async (event) => {
    event.preventDefault()
    if (unsupported.length) {
      setError(
        `Every diagnosis needs a service line: add one for ${unsupported.map((d) => d.code || `Dx ${d.index + 1}`).join(', ')}`,
      )
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      setResult(await createClaim(toRequest(form, lists.procedures)))
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const reset = () => {
    setForm(emptyForm())
    setResult(null)
    setError(null)
  }

  return (
    <div className="space-y-4 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">New Claim</h1>
        <p className="text-sm text-gray-500">
          Enter a draft claim for a registered patient and validate it against the enabled
          rules. Mark it submitted once the errors are resolved. New claims are kept until the
          server restarts.
        </p>
      </div>

      {lists.error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          Could not load the form’s lists — {lists.error}
        </div>
      )}

      <form
        onSubmit={submit}
        aria-busy={submitting}
        className="relative max-w-3xl rounded-xl border border-gray-100 bg-white p-5 shadow-sm"
      >
        <fieldset disabled={submitting || result !== null} className="space-y-5">
          <FormSection title="Patient" hint="Claims can only be entered for patients registered with the hospital">
            <PatientPicker patient={form.patient} payers={payers} onChange={choosePatient} />
          </FormSection>

          <FormSection title="Coverage" hint="Defaults to the patient’s registered primary payer">
            <CoverageFields
              patient={form.patient}
              payers={payers}
              payerId={form.payer_id}
              otherPayerIds={form.other_payer_ids}
              onChange={change}
            />
          </FormSection>

          <FormSection title="Encounter">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field
                label="Rendering provider"
                htmlFor={id('provider')}
                hint={
                  provider
                    ? `Department: ${departments[provider.department_id]?.department_name ?? provider.department_id}`
                    : 'The claim’s department follows the provider'
                }
              >
                <ProviderSelect
                  id={id('provider')}
                  providers={lists.providers}
                  departments={departments}
                  value={form.provider_id}
                  onChange={(provider_id) => change({ provider_id })}
                />
              </Field>
              <Field label="Facility" htmlFor={id('facility')}>
                <select
                  id={id('facility')}
                  className={INPUT_CLASS}
                  value={form.facility_id}
                  onChange={(e) => change({ facility_id: e.target.value })}
                >
                  {Object.values(lists.facilities).map((facility) => (
                    <option key={facility.facility_id} value={facility.facility_id}>
                      {facility.facility_name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Claim type" htmlFor={id('type')}>
                <select
                  id={id('type')}
                  className={INPUT_CLASS}
                  value={form.claim_type}
                  onChange={(e) => change({ claim_type: e.target.value })}
                >
                  {CLAIM_TYPES.map((type) => (
                    <option key={type}>{type}</option>
                  ))}
                </select>
              </Field>
              <Field label="Place of service" htmlFor={id('pos')}>
                <select
                  id={id('pos')}
                  className={INPUT_CLASS}
                  value={form.place_of_service}
                  onChange={(e) => change({ place_of_service: e.target.value })}
                >
                  {PLACES_OF_SERVICE.map(({ value, label }) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Service date" htmlFor={id('service')}>
                <input
                  id={id('service')}
                  type="date"
                  required
                  className={INPUT_CLASS}
                  value={form.service_date}
                  onChange={(e) => change({ service_date: e.target.value })}
                />
              </Field>
              <Field
                label="Planned submission date"
                htmlFor={id('submission')}
                hint="Replaced by the actual date when you mark the claim submitted"
              >
                <input
                  id={id('submission')}
                  type="date"
                  required
                  min={form.service_date || undefined}
                  className={INPUT_CLASS}
                  value={form.submission_date}
                  onChange={(e) => change({ submission_date: e.target.value })}
                />
              </Field>
            </div>
          </FormSection>

          <FormSection title="Diagnoses" hint="Primary first. Every diagnosis must be supported by a service line.">
            <DiagnosisList
              diagnoses={form.diagnoses}
              known={lists.diagnoses}
              onChange={changeDiagnoses}
              onRemove={removeDiagnosis}
            />
          </FormSection>

          <FormSection title="Services rendered" hint="Each line names the diagnosis it treats">
            <ServiceLines
              lines={form.lines}
              diagnoses={form.diagnoses}
              procedures={lists.procedures}
              onChange={(lines) => change({ lines })}
              onAdd={() => change({ lines: [...form.lines, emptyLine()] })}
            />
            {unsupported.length > 0 && (
              <p className="text-sm text-amber-700">
                No service line treats{' '}
                {unsupported.map((d) => d.code || `Dx ${d.index + 1}`).join(', ')} yet.
              </p>
            )}
          </FormSection>

          <FormSection title="Prior authorization">
            <ToggleField
              label="Prior auth required"
              checked={form.pa_required}
              onChange={(pa_required) => change({ pa_required })}
            />
            {form.pa_required && (
              <ToggleField
                label="Prior auth obtained"
                checked={form.pa_obtained}
                onChange={(pa_obtained) => change({ pa_obtained })}
              />
            )}
            {form.pa_required && form.pa_obtained && (
              <div className="sm:max-w-xs">
                <Field label="Prior auth number" htmlFor={id('pa-number')}>
                  <input
                    id={id('pa-number')}
                    autoComplete="off"
                    className={INPUT_CLASS}
                    value={form.pa_number}
                    onChange={(e) => change({ pa_number: e.target.value })}
                  />
                </Field>
              </div>
            )}
          </FormSection>
        </fieldset>

        {error && (
          <p role="alert" className="mt-5 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            Could not create the claim — {error}
          </p>
        )}

        {result === null && (
          <button
            type="submit"
            disabled={submitting}
            className="mt-5 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
          >
            {submitting ? 'Creating & validating…' : 'Create & validate claim'}
          </button>
        )}
      </form>

      {result && <ValidationResult result={result} onReset={reset} onSubmitted={setResult} />}
    </div>
  )
}
