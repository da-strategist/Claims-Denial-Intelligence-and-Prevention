// Sections of the New Claim form: patient, coverage, diagnoses, and service lines
import { useId, useState } from 'react'
import { FIELD_CLASS, INPUT_CLASS } from '../constants'
import { REVENUE_CODES } from '../utils/billing'
import { PolicyFields } from './BillingFields'
import { usePatientSearch } from '../hooks/useClaimEntry'
import { useDebouncedValue } from '../hooks/useClaims'
import { lineCharge, MAX_DIAGNOSES, MAX_OTHER_PAYERS } from '../utils/claimEntry'
import { currency } from '../utils/format'

const PAYER_ORDER = ['Secondary', 'Tertiary']

const SMALL_BUTTON =
  'btn-secondary btn-sm'
const REMOVE_BUTTON =
  'rounded-lg px-2 py-1.5 text-sm text-gray-400 hover:bg-red-50 hover:text-red-700 disabled:invisible'

export function FormSection({ title, hint, children }) {
  return (
    <fieldset className="space-y-3 border-t border-gray-100 pt-4 first:border-0 first:pt-0">
      <legend className="float-left w-full">
        <span className="block text-sm font-semibold text-gray-900">{title}</span>
        {hint && <span className="block text-xs font-normal text-gray-500">{hint}</span>}
      </legend>
      <div className="clear-both space-y-3">{children}</div>
    </fieldset>
  )
}

function patientLine(patient, payers) {
  const payer = payers[patient.primary_payer_id]?.payer_name ?? patient.primary_payer_id
  return `${patient.patient_id} · ${patient.age} ${patient.gender} · ZIP ${patient.zip_code} · ${payer}`
}

function History({ patient }) {
  return (
    <span className="text-xs text-gray-500">
      {patient.claim_count} claim{patient.claim_count === 1 ? '' : 's'}
      {patient.denial_count > 0 && (
        <span className="text-amber-700">
          {' '}
          · {patient.denial_count} denial{patient.denial_count === 1 ? '' : 's'}
        </span>
      )}
    </span>
  )
}

/** Search registered patients and pick one. */
export function PatientPicker({ patient, payers, onChange }) {
  const inputId = useId()
  const [term, setTerm] = useState('')
  const search = useDebouncedValue(term.trim())
  const { data, loading, error } = usePatientSearch(search)

  if (patient) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-gray-50 p-4">
        <div>
          <div className="font-semibold text-gray-900">
            {patient.first_name} {patient.last_name}
          </div>
          <div className="text-sm text-gray-600">{patientLine(patient, payers)}</div>
          <History patient={patient} />
        </div>
        <button type="button" className={SMALL_BUTTON} onClick={() => onChange(null)}>
          Change patient
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <label htmlFor={inputId} className="sr-only">
        Search registered patients
      </label>
      <input
        id={inputId}
        type="search"
        autoComplete="off"
        placeholder="Search by name or patient ID (e.g. Karen Sanchez, PAT000002)"
        className={INPUT_CLASS}
        value={term}
        onChange={(e) => setTerm(e.target.value)}
      />
      {/* Required: a hidden-but-focusable proxy so the browser blocks submit without a patient */}
      <input
        tabIndex={-1}
        required
        aria-hidden="true"
        value=""
        onChange={() => {}}
        onInvalid={(e) => e.target.setCustomValidity('Select a registered patient')}
        className="pointer-events-none absolute h-0 w-0 opacity-0"
      />
      {error && <p className="text-sm text-red-700">Could not search patients — {error}</p>}
      {search && data && (
        <div className="rounded-xl ring-1 ring-gray-200/70">
          {data.items.length === 0 ? (
            <p className="p-3 text-sm text-gray-500">
              No registered patient matches “{search}”. Patients must be registered by the
              hospital before a claim can be entered.
            </p>
          ) : (
            <ul aria-label="Matching patients" className="divide-y divide-gray-100">
              {data.items.map((match) => (
                <li key={match.patient_id}>
                  <button
                    type="button"
                    className="w-full px-3 py-2 text-left hover:bg-gray-50 focus:bg-red-50 focus:outline-none"
                    onClick={() => onChange(match)}
                  >
                    <span className="font-medium text-gray-900">
                      {match.first_name} {match.last_name}
                    </span>{' '}
                    <span className="text-sm text-gray-600">{patientLine(match, payers)}</span>
                    <span className="ml-2">
                      <History patient={match} />
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {data.total > data.items.length && (
            <p className="border-t border-gray-100 px-3 py-1.5 text-xs text-gray-500">
              Showing {data.items.length} of {data.total.toLocaleString()} — add more of the
              name or the patient ID to narrow it down.
            </p>
          )}
        </div>
      )}
      {search && loading && !data && <p className="text-sm text-gray-500">Searching…</p>}
    </div>
  )
}

function payerOptions(payers) {
  return Object.values(payers).sort((a, b) => a.payer_name.localeCompare(b.payer_name))
}

/**
 * Billed payer (defaults to the patient's primary) plus secondary/tertiary coverage, each
 * with its policy. `policies` is [billed, ...others]; self-pay needs none.
 */
export function CoverageFields({ patient, payers, payerId, otherPayerIds, policies, onChange, onPolicyChange }) {
  const baseId = useId()
  const options = payerOptions(payers)
  const primary = patient?.primary_payer_id
  const taken = (except) => new Set([payerId, ...otherPayerIds].filter((id) => id !== except))

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <label htmlFor={`${baseId}-billed`} className="block text-sm font-medium text-gray-800">
          Billed payer
        </label>
        <select
          id={`${baseId}-billed`}
          required
          className={INPUT_CLASS}
          value={payerId}
          onChange={(e) => onChange({ payer_id: e.target.value })}
        >
          <option value="">Select a payer…</option>
          {options.map((payer) => (
            <option key={payer.payer_id} value={payer.payer_id} disabled={taken(payerId).has(payer.payer_id)}>
              {payer.payer_name}
              {payer.payer_id === primary ? ' (registered primary)' : ''}
            </option>
          ))}
        </select>
        {payerId && primary && payerId !== primary && (
          <p className="text-xs text-amber-700">
            Differs from the patient’s registered primary payer (
            {payers[primary]?.payer_name ?? primary}). Confirm eligibility and coordination of
            benefits before submitting.
          </p>
        )}
      </div>
      {payerId &&
        (payers[payerId]?.payer_type === 'Self-Pay' ? (
          <p className="text-sm text-gray-500">Self-pay is billed to the patient, so no policy is needed.</p>
        ) : (
          <PolicyFields
            payerName={payers[payerId]?.payer_name ?? payerId}
            policy={policies[0]}
            onChange={(policy) => onPolicyChange(0, policy)}
          />
        ))}

      {otherPayerIds.map((id, index) => (
        <div key={index} className="flex items-end gap-2">
          <div className="flex-1 space-y-1">
            <label htmlFor={`${baseId}-other-${index}`} className="block text-sm font-medium text-gray-800">
              {PAYER_ORDER[index]} payer
            </label>
            <select
              id={`${baseId}-other-${index}`}
              required
              className={INPUT_CLASS}
              value={id}
              onChange={(e) =>
                onChange({
                  other_payer_ids: otherPayerIds.map((v, i) => (i === index ? e.target.value : v)),
                })
              }
            >
              <option value="">Select a payer…</option>
              {options.map((payer) => (
                <option key={payer.payer_id} value={payer.payer_id} disabled={taken(id).has(payer.payer_id)}>
                  {payer.payer_name}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            className={REMOVE_BUTTON}
            aria-label={`Remove ${PAYER_ORDER[index].toLowerCase()} payer`}
            onClick={() => onChange({ other_payer_ids: otherPayerIds.filter((_, i) => i !== index) })}
          >
            ✕
          </button>
        </div>
      )).flatMap((row, index) => [
        row,
        otherPayerIds[index] && policies[index + 1] ? (
          <PolicyFields
            key={`policy-${index}`}
            payerName={payers[otherPayerIds[index]]?.payer_name ?? otherPayerIds[index]}
            policy={policies[index + 1]}
            onChange={(policy) => onPolicyChange(index + 1, policy)}
          />
        ) : null,
      ])}
      {otherPayerIds.length < MAX_OTHER_PAYERS && (
        <button
          type="button"
          className={SMALL_BUTTON}
          onClick={() => onChange({ other_payer_ids: [...otherPayerIds, ''] })}
        >
          + Add {PAYER_ORDER[otherPayerIds.length].toLowerCase()} payer
        </button>
      )}
    </div>
  )
}

/** Primary diagnosis first, then up to 11 more. */
export function DiagnosisList({ diagnoses, known, onChange, onRemove }) {
  const baseId = useId()
  const listId = `${baseId}-codes`
  return (
    <div className="space-y-2">
      <datalist id={listId}>
        {Object.values(known).map((code) => (
          <option key={code.icd10_code} value={code.icd10_code}>
            {code.description}
          </option>
        ))}
      </datalist>
      {diagnoses.map((code, index) => (
        <div key={index} className="flex items-center gap-2">
          <label htmlFor={`${baseId}-${index}`} className="w-20 shrink-0 text-sm text-gray-600">
            {index === 0 ? 'Primary' : `Dx ${index + 1}`}
          </label>
          <input
            id={`${baseId}-${index}`}
            required
            list={listId}
            pattern="[A-Z][0-9]{2}(\.[A-Z0-9]{1,4})?"
            title="An ICD-10 code such as E11.65 or I10"
            autoComplete="off"
            className={`${FIELD_CLASS} w-32 font-mono uppercase`}
            value={code}
            onChange={(e) =>
              onChange(diagnoses.map((v, i) => (i === index ? e.target.value.toUpperCase() : v)))
            }
          />
          <span className="min-w-0 flex-1 truncate text-sm text-gray-500">
            {known[code]?.description}
          </span>
          <button
            type="button"
            className={REMOVE_BUTTON}
            aria-label={`Remove diagnosis ${index + 1}`}
            disabled={diagnoses.length === 1}
            onClick={() => onRemove(index)}
          >
            ✕
          </button>
        </div>
      ))}
      {diagnoses.length < MAX_DIAGNOSES && (
        <button type="button" className={SMALL_BUTTON} onClick={() => onChange([...diagnoses, ''])}>
          + Add diagnosis
        </button>
      )}
    </div>
  )
}

/** Services rendered; each points at the diagnosis it treats. */
export function ServiceLines({ lines, diagnoses, procedures, institutional = false, onChange, onAdd }) {
  const baseId = useId()
  const codes = Object.values(procedures).sort((a, b) => a.cpt_code.localeCompare(b.cpt_code))
  const update = (key, changes) =>
    onChange(lines.map((line) => (line.key === key ? { ...line, ...changes } : line)))
  const total = lines.reduce((sum, line) => sum + lineCharge(line, procedures), 0)

  return (
    <div className="space-y-2">
      {institutional && (
        <datalist id={`${baseId}-revenue-codes`}>
          {REVENUE_CODES.map(([code, label]) => (
            <option key={code} value={code}>
              {label}
            </option>
          ))}
        </datalist>
      )}
      <ol className="space-y-3">
        {lines.map((line, index) => {
          const id = (name) => `${baseId}-${line.key}-${name}`
          const standard = procedures[line.cpt_code]?.standard_charge
          return (
            <li key={line.key} className="rounded-xl bg-gray-50 p-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="eyebrow">
                  Line {index + 1}
                </span>
                <button
                  type="button"
                  className={REMOVE_BUTTON}
                  aria-label={`Remove line ${index + 1}`}
                  disabled={lines.length === 1}
                  onClick={() => onChange(lines.filter((l) => l.key !== line.key))}
                >
                  ✕
                </button>
              </div>
              <div
                className={`grid grid-cols-2 gap-2 ${
                  institutional
                    ? 'sm:grid-cols-[5.5rem_minmax(0,2fr)_4.5rem_4.5rem_6.5rem_minmax(0,1fr)]'
                    : 'sm:grid-cols-[minmax(0,2fr)_5rem_5rem_7rem_minmax(0,1fr)]'
                }`}
              >
                {institutional && (
                  <div className="col-span-2 space-y-1 sm:col-span-1">
                    <label htmlFor={id('revenue')} className="block text-xs text-gray-600">
                      Revenue code
                    </label>
                    <input
                      id={id('revenue')}
                      required
                      list={`${baseId}-revenue-codes`}
                      inputMode="numeric"
                      pattern="\d{4}"
                      title="Four digits, e.g. 0450"
                      autoComplete="off"
                      className={`${INPUT_CLASS} font-mono`}
                      value={line.revenue_code}
                      onChange={(e) => update(line.key, { revenue_code: e.target.value.replace(/\D/g, '').slice(0, 4) })}
                    />
                  </div>
                )}
                <div className="col-span-2 space-y-1 sm:col-span-1">
                  <label htmlFor={id('cpt')} className="block text-xs text-gray-600">
                    Procedure (CPT)
                  </label>
                  <select
                    id={id('cpt')}
                    required
                    className={INPUT_CLASS}
                    value={line.cpt_code}
                    onChange={(e) => update(line.key, { cpt_code: e.target.value })}
                  >
                    <option value="">Select…</option>
                    {codes.map((code) => (
                      <option key={code.cpt_code} value={code.cpt_code}>
                        {code.cpt_code} — {code.description}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <label htmlFor={id('units')} className="block text-xs text-gray-600">
                    Units
                  </label>
                  <input
                    id={id('units')}
                    type="number"
                    required
                    min="1"
                    max="99"
                    className={INPUT_CLASS}
                    value={line.units}
                    onChange={(e) => update(line.key, { units: e.target.value })}
                  />
                </div>
                <div className="space-y-1">
                  <label htmlFor={id('modifier')} className="block text-xs text-gray-600">
                    Modifier
                  </label>
                  <input
                    id={id('modifier')}
                    maxLength={2}
                    pattern="[A-Z0-9]{2}"
                    title="Two letters or digits, e.g. 25 or 59"
                    autoComplete="off"
                    className={`${INPUT_CLASS} font-mono uppercase`}
                    value={line.modifier}
                    onChange={(e) => update(line.key, { modifier: e.target.value.toUpperCase() })}
                  />
                </div>
                <div className="space-y-1">
                  <label htmlFor={id('charge')} className="block text-xs text-gray-600">
                    Charge
                  </label>
                  <input
                    id={id('charge')}
                    type="number"
                    min="0"
                    step="0.01"
                    inputMode="decimal"
                    placeholder={
                      standard === undefined ? '' : String(standard * (Number(line.units) || 0))
                    }
                    className={INPUT_CLASS}
                    value={line.charge}
                    onChange={(e) => update(line.key, { charge: e.target.value })}
                  />
                </div>
                <div className="col-span-2 space-y-1 sm:col-span-1">
                  <label htmlFor={id('dx')} className="block text-xs text-gray-600">
                    Diagnosis treated
                  </label>
                  <select
                    id={id('dx')}
                    className={INPUT_CLASS}
                    value={line.dx}
                    onChange={(e) => update(line.key, { dx: Number(e.target.value) })}
                  >
                    {diagnoses.map((code, i) => (
                      <option key={i} value={i}>
                        {code || `Dx ${i + 1} (blank)`}
                        {i === 0 ? ' · primary' : ''}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </li>
          )
        })}
      </ol>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button type="button" className={SMALL_BUTTON} onClick={onAdd}>
          + Add service line
        </button>
        <span className="text-sm text-gray-700">
          Total charge{' '}
          <span className="font-semibold tabular-nums text-gray-900">{currency.format(total)}</span>
        </span>
      </div>
      <p className="text-xs text-gray-500">
        A blank charge uses the procedure’s standard charge × units.
      </p>
    </div>
  )
}
