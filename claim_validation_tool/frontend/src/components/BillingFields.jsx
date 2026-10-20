// What the 837 claim file needs beyond the claim: patient details, policies, and UB-04 codes
import { useId } from 'react'
import { INPUT_CLASS } from '../constants'
import {
  ADMISSION_SOURCES,
  ADMISSION_TYPES,
  PATIENT_STATUSES,
  RELATIONSHIPS,
  SEXES,
  TYPES_OF_BILL,
} from '../utils/billing'

function Labelled({ id, label, children, className = '' }) {
  return (
    <div className={`space-y-1 ${className}`}>
      <label htmlFor={id} className="block text-xs text-gray-600">
        {label}
      </label>
      {children}
    </div>
  )
}

function Select({ id, value, options, onChange, required = true }) {
  return (
    <select id={id} required={required} className={INPUT_CLASS} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">Select…</option>
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  )
}

/** Date of birth and address. Sex comes from the hospital registration. */
export function PatientDetails({ details, sex, onChange }) {
  const base = useId()
  const address = details.patient_address
  const setAddress = (changes) => onChange({ patient_address: { ...address, ...changes } })
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-6">
      <Labelled id={`${base}-dob`} label="Date of birth" className="col-span-1 sm:col-span-2">
        <input
          id={`${base}-dob`}
          type="date"
          required
          className={INPUT_CLASS}
          value={details.patient_birth_date}
          onChange={(e) => onChange({ patient_birth_date: e.target.value })}
        />
      </Labelled>
      <div className="col-span-1 space-y-1 sm:col-span-4">
        <span className="block text-xs text-gray-600">Sex (from registration)</span>
        <span className="block py-2 text-sm text-gray-900">
          {SEXES.find((s) => s.value === sex)?.label ?? 'Unknown'}
        </span>
      </div>
      <Labelled id={`${base}-line1`} label="Street address" className="col-span-2 sm:col-span-4">
        <input
          id={`${base}-line1`}
          required
          autoComplete="off"
          maxLength={55}
          className={INPUT_CLASS}
          value={address.line1}
          onChange={(e) => setAddress({ line1: e.target.value })}
        />
      </Labelled>
      <Labelled id={`${base}-line2`} label="Apt, suite (optional)" className="col-span-2 sm:col-span-2">
        <input
          id={`${base}-line2`}
          autoComplete="off"
          maxLength={55}
          className={INPUT_CLASS}
          value={address.line2}
          onChange={(e) => setAddress({ line2: e.target.value })}
        />
      </Labelled>
      <Labelled id={`${base}-city`} label="City" className="col-span-2 sm:col-span-3">
        <input
          id={`${base}-city`}
          required
          autoComplete="off"
          className={INPUT_CLASS}
          value={address.city}
          onChange={(e) => setAddress({ city: e.target.value })}
        />
      </Labelled>
      <Labelled id={`${base}-state`} label="State" className="sm:col-span-1">
        <input
          id={`${base}-state`}
          required
          maxLength={2}
          pattern="[A-Z]{2}"
          title="Two-letter state code, e.g. NC"
          autoComplete="off"
          className={`${INPUT_CLASS} uppercase`}
          value={address.state}
          onChange={(e) => setAddress({ state: e.target.value.toUpperCase() })}
        />
      </Labelled>
      <Labelled id={`${base}-zip`} label="ZIP code" className="sm:col-span-2">
        <input
          id={`${base}-zip`}
          required
          inputMode="numeric"
          pattern="\d{5}(\d{4})?"
          title="5 or 9 digits"
          autoComplete="off"
          className={INPUT_CLASS}
          value={address.zip_code}
          onChange={(e) => setAddress({ zip_code: e.target.value.replace(/\D/g, '').slice(0, 9) })}
        />
      </Labelled>
    </div>
  )
}

/** One payer's policy: member ID and who holds it (their details if not the patient). */
export function PolicyFields({ payerName, policy, onChange }) {
  const base = useId()
  const set = (changes) => onChange({ ...policy, ...changes })
  const holder = policy.relationship !== 'self'
  return (
    <div className="grid grid-cols-2 gap-3 rounded-xl bg-gray-50 p-4 sm:grid-cols-6">
      <Labelled id={`${base}-member`} label={`${payerName} member ID`} className="col-span-2 sm:col-span-3">
        <input
          id={`${base}-member`}
          required
          autoComplete="off"
          pattern="[A-Za-z0-9\-]{2,30}"
          title="2–30 letters, digits, or hyphens"
          className={`${INPUT_CLASS} font-mono`}
          value={policy.member_id}
          onChange={(e) => set({ member_id: e.target.value.trim() })}
        />
      </Labelled>
      <Labelled id={`${base}-group`} label="Group number (optional)" className="sm:col-span-3">
        <input
          id={`${base}-group`}
          autoComplete="off"
          pattern="[A-Za-z0-9\-]{1,30}"
          className={`${INPUT_CLASS} font-mono`}
          value={policy.group_number}
          onChange={(e) => set({ group_number: e.target.value.trim() })}
        />
      </Labelled>
      <Labelled id={`${base}-rel`} label="Patient is the policy holder’s" className="sm:col-span-3">
        <select
          id={`${base}-rel`}
          className={INPUT_CLASS}
          value={policy.relationship}
          onChange={(e) => set({ relationship: e.target.value })}
        >
          {RELATIONSHIPS.map((r) => (
            <option key={r.value} value={r.value}>
              {r.value === 'self' ? 'Self (patient holds the policy)' : r.label}
            </option>
          ))}
        </select>
      </Labelled>
      {holder && (
        <>
          <Labelled id={`${base}-first`} label="Holder first name" className="sm:col-span-3">
            <input id={`${base}-first`} required autoComplete="off" className={INPUT_CLASS} value={policy.first_name} onChange={(e) => set({ first_name: e.target.value })} />
          </Labelled>
          <Labelled id={`${base}-last`} label="Holder last name" className="sm:col-span-3">
            <input id={`${base}-last`} required autoComplete="off" className={INPUT_CLASS} value={policy.last_name} onChange={(e) => set({ last_name: e.target.value })} />
          </Labelled>
          <Labelled id={`${base}-hdob`} label="Holder date of birth" className="sm:col-span-2">
            <input id={`${base}-hdob`} type="date" required className={INPUT_CLASS} value={policy.birth_date} onChange={(e) => set({ birth_date: e.target.value })} />
          </Labelled>
          <Labelled id={`${base}-hsex`} label="Holder sex" className="sm:col-span-1">
            <Select id={`${base}-hsex`} value={policy.sex} options={SEXES} onChange={(sex) => set({ sex })} />
          </Labelled>
        </>
      )}
    </div>
  )
}

/** UB-04 header codes for an institutional claim. */
export function InstitutionalFields({ details, onChange }) {
  const base = useId()
  const set = (key) => (value) => onChange({ ...details, [key]: value })
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <Labelled id={`${base}-tob`} label="Type of bill">
        <Select id={`${base}-tob`} value={details.type_of_bill} options={TYPES_OF_BILL} onChange={set('type_of_bill')} />
      </Labelled>
      <Labelled id={`${base}-type`} label="Admission type">
        <Select id={`${base}-type`} value={details.admission_type} options={ADMISSION_TYPES} onChange={set('admission_type')} />
      </Labelled>
      <Labelled id={`${base}-source`} label="Point of origin">
        <Select id={`${base}-source`} value={details.admission_source} options={ADMISSION_SOURCES} onChange={set('admission_source')} />
      </Labelled>
      <Labelled id={`${base}-status`} label="Patient status">
        <Select id={`${base}-status`} value={details.patient_status} options={PATIENT_STATUSES} onChange={set('patient_status')} />
      </Labelled>
    </div>
  )
}
