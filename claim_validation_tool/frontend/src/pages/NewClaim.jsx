import PageHeader, { Notice, Page } from '../components/PageHeader'
import { useId, useState } from 'react'
import {
  CoverageFields,
  DiagnosisList,
  FormSection,
  PatientPicker,
  ServiceLines,
} from '../components/ClaimEntryFields'
import { InstitutionalFields, PatientDetails } from '../components/BillingFields'
import ClaimDetailPanel from '../components/ClaimDetailPanel'
import DraftsPanel from '../components/DraftsPanel'
import EdiFileCard from '../components/EdiFileCard'
import Icon from '../components/Icon'
import { ClaimStatusBadge } from '../components/StatusBadge'
import Toggle from '../components/Toggle'
import { CLAIM_TYPES, INPUT_CLASS, PLACES_OF_SERVICE } from '../constants'
import { useClaimEntryLists } from '../hooks/useClaimEntry'
import { useClaimDetail, useClaimValidations, useClaims, usePayerLookup } from '../hooks/useClaims'
import { useDepartmentLookup } from '../hooks/useRules'
import { useApi } from '../hooks/useApi'
import {
  createClaim,
  deleteDraft,
  getDraft,
  getPatientRegistration,
  listDrafts,
  saveDraft,
} from '../services/api'
import { emptyPolicy } from '../utils/billing'
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
const emptyLine = (dx = 0) => ({
  key: nextLineKey++,
  cpt_code: '',
  units: '1',
  modifier: '',
  charge: '',
  dx,
  revenue_code: '',
})

const emptyBilling = () => ({
  patient_birth_date: '',
  patient_address: { line1: '', line2: '', city: '', state: '', zip_code: '' },
  policy: emptyPolicy(),
  other_policies: [],
  institutional: { type_of_bill: '131', admission_type: '3', admission_source: '1', patient_status: '01' },
})

/** A registered policy in the form's shape (blank strings rather than nulls). */
function policyFromRegistration(registration, payerId) {
  const saved = registration?.policies?.[payerId]
  if (!saved) return emptyPolicy()
  return Object.fromEntries(Object.entries(emptyPolicy()).map(([key, blank]) => [key, saved[key] ?? blank]))
}

/** A policy as the API takes it: holder details only when the patient isn't the holder. */
function policyRequest(policy) {
  const base = {
    member_id: policy.member_id.trim(),
    group_number: policy.group_number.trim() || null,
    relationship: policy.relationship,
  }
  if (policy.relationship === 'self') return base
  const { first_name, last_name, birth_date, sex } = policy
  return { ...base, first_name, last_name, birth_date, sex }
}

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
  billing: emptyBilling(),
  // The patient's registration the billing fields were filled from (not sent)
  registration: null,
})

/** The form as a saved draft: as typed, nothing required. The patient goes by ID. */
function toDraft(form) {
  return {
    patient_id: form.patient?.patient_id ?? null,
    payer_id: form.payer_id,
    other_payer_ids: form.other_payer_ids,
    provider_id: form.provider_id,
    facility_id: form.facility_id,
    diagnoses: form.diagnoses,
    lines: form.lines.map(({ cpt_code, units, modifier, charge, dx, revenue_code }) => ({
      cpt_code,
      units: String(units),
      modifier,
      charge: String(charge),
      dx,
      revenue_code,
    })),
    claim_type: form.claim_type,
    place_of_service: form.place_of_service,
    service_date: form.service_date,
    submission_date: form.submission_date,
    pa_required: form.pa_required,
    pa_obtained: form.pa_obtained,
    pa_number: form.pa_number,
    billing: form.billing,
  }
}

/** A saved draft back into the form (its patient comes resolved from the API). */
function fromDraft({ form, patient }) {
  const blank = emptyForm()
  return {
    ...blank,
    patient,
    payer_id: form.payer_id ?? '',
    other_payer_ids: form.other_payer_ids,
    provider_id: form.provider_id ?? '',
    facility_id: form.facility_id ?? DEFAULT_FACILITY,
    diagnoses: form.diagnoses.length ? form.diagnoses : [''],
    lines: form.lines.length
      ? form.lines.map((line) => ({ ...emptyLine(), ...line, key: nextLineKey++ }))
      : blank.lines,
    claim_type: form.claim_type,
    place_of_service: form.place_of_service,
    service_date: form.service_date ?? '',
    submission_date: form.submission_date ?? blank.submission_date,
    pa_required: form.pa_required,
    pa_obtained: form.pa_obtained,
    pa_number: form.pa_number,
    billing: {
      ...blank.billing,
      ...form.billing,
      patient_address: { ...blank.billing.patient_address, ...form.billing?.patient_address },
      institutional: { ...blank.billing.institutional, ...form.billing?.institutional },
    },
  }
}

/** Request body. Lines point at diagnoses by position in the form; send the codes. */
function toRequest(form, procedures, payers) {
  const paObtained = form.pa_required && form.pa_obtained
  const institutional = form.claim_type === 'Institutional'
  const { patient_address: address } = form.billing
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
      revenue_code: institutional ? line.revenue_code : null,
    })),
    claim_type: form.claim_type,
    place_of_service: form.place_of_service,
    service_date: form.service_date,
    submission_date: form.submission_date,
    pa_required: form.pa_required,
    pa_obtained: paObtained,
    pa_number: paObtained && form.pa_number.trim() ? form.pa_number.trim() : null,
    billing: {
      patient_birth_date: form.billing.patient_birth_date,
      patient_address: { ...address, line2: address.line2.trim() || null },
      policy: payers[form.payer_id]?.payer_type === 'Self-Pay' ? null : policyRequest(form.billing.policy),
      other_policies: form.billing.other_policies.map(policyRequest),
      institutional: institutional ? form.billing.institutional : null,
    },
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

/** Where the filled-in details came from, so a biller knows to check sample data. */
function RegistrationNote({ registration, patient }) {
  if (!registration) return null
  return (
    <p className="text-xs text-gray-500">
      {registration.source === 'sample'
        ? `Filled from ${patient.first_name} ${patient.last_name}’s registration (sample details). Check them before creating the claim.`
        : `Filled from ${patient.first_name} ${patient.last_name}’s last claim${registration.updated_by ? `, entered by ${registration.updated_by}` : ''}. Saved for next time when you create this claim.`}
    </p>
  )
}

/** A created claim that hasn't been submitted: its problems, fixes, and submission. */
function DraftClaimView({ claimId, justCreated, onClose, onChanged }) {
  const { data: claim, error, reload } = useClaimDetail(claimId)
  const changed = () => {
    reload()
    onChanged()
  }
  if (error) return <Notice>Could not load {claimId} — {error}</Notice>
  if (!claim) return <div className="card h-64 animate-pulse" />
  const patient = claim.patient
    ? `${claim.patient.first_name} ${claim.patient.last_name} (${claim.patient_id})`
    : claim.patient_id
  return (
    <section aria-labelledby="draft-claim-title" className="card space-y-6 p-6 sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 id="draft-claim-title" className="text-xl font-semibold tracking-tight text-gray-900">
              {justCreated ? `Created ${claim.claim_id}` : claim.claim_id}
            </h2>
            <ClaimStatusBadge status={claim.status} />
          </div>
          <p className="mt-1 text-sm text-gray-500">
            {patient} · {claim.payer?.payer_name ?? claim.payer_id} · {claim.lines.length} line
            {claim.lines.length === 1 ? '' : 's'} · {currency.format(claim.total_charge)}
          </p>
        </div>
        <button type="button" onClick={onClose} className="btn-secondary btn-sm">
          <Icon name="plus" className="h-4 w-4" strokeWidth={2} />
          New claim
        </button>
      </div>
      {claim.status === 'Draft' ? (
        <ClaimDetailPanel claim={claim} onClaimChanged={changed} stacked />
      ) : (
        <div className="space-y-4">
          <Notice tone="info">
            Submitted — it’s now {claim.status} and listed under{' '}
            <a className="font-medium text-accent hover:underline" href={routeHref('#/claims', { search: claim.claim_id })}>
              Claims
            </a>
            .
          </Notice>
          <EdiFileCard claimId={claim.claim_id} edi={claim.edi} />
        </div>
      )}
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
  // The draft claim shown instead of the form (just created, or opened from the panel)
  const [openClaim, setOpenClaim] = useState(null) // { id, justCreated }
  // The saved draft this form came from or was saved as, and when it was last saved
  const [draft, setDraft] = useState({ id: null, savedAt: null, saving: false, error: null })
  const drafts = useApi((options) => listDrafts(options))
  const draftClaims = useClaims({ status: 'Draft', sort_by: 'service_date', sort_desc: true, page_size: 100 })
  const draftClaimIds = (draftClaims.data?.items ?? []).map((claim) => claim.claim_id)
  const draftValidations = useClaimValidations(draftClaimIds)
  const reloadDraftClaims = () => {
    draftClaims.reload()
    draftValidations.reload()
  }

  const change = (changes) => setForm((prev) => ({ ...prev, ...changes }))

  const saveAsDraft = async () => {
    setDraft((prev) => ({ ...prev, saving: true, error: null }))
    try {
      const saved = await saveDraft(toDraft(form), draft.id)
      setDraft({ id: saved.id, savedAt: new Date(saved.updated_at), saving: false, error: null })
      drafts.reload()
    } catch (err) {
      setDraft((prev) => ({ ...prev, saving: false, error: err.message }))
    }
  }

  const openDraft = async (row) => {
    setError(null)
    try {
      const saved = await getDraft(row.id)
      setForm(fromDraft(saved))
      setOpenClaim(null)
      setDraft({ id: saved.id, savedAt: new Date(saved.updated_at), saving: false, error: null })
      window.scrollTo?.({ top: 0, behavior: 'smooth' })
    } catch (err) {
      setDraft((prev) => ({ ...prev, error: err.message }))
      drafts.reload()
    }
  }

  const removeDraft = async (row) => {
    try {
      await deleteDraft(row.id)
    } catch {
      // Already gone (expired or removed by someone else): the reload shows that
    }
    if (row.id === draft.id) setDraft({ id: null, savedAt: null, saving: false, error: null })
    drafts.reload()
  }

  const changeBilling = (changes) =>
    setForm((prev) => ({ ...prev, billing: { ...prev.billing, ...changes } }))

  // A new patient brings their registered primary payer as the default billed payer, and
  // their registered date of birth, address, and policy fill the billing fields
  const choosePatient = async (patient) => {
    change({
      patient,
      payer_id: patient?.primary_payer_id ?? '',
      other_payer_ids: [],
      billing: emptyBilling(),
      registration: null,
    })
    if (!patient) return
    try {
      const registration = await getPatientRegistration(patient.patient_id)
      setForm((prev) =>
        prev.patient?.patient_id !== patient.patient_id
          ? prev
          : {
              ...prev,
              registration,
              billing: {
                ...prev.billing,
                patient_birth_date: registration.birth_date,
                patient_address: { ...emptyBilling().patient_address, ...registration.address, line2: registration.address.line2 ?? '' },
                policy: policyFromRegistration(registration, prev.payer_id),
              },
            },
      )
    } catch {
      // Nothing registered to fill in: the fields stay blank for typing
    }
  }

  // Each payer keeps a policy; a newly chosen payer's comes from the registration
  const changeCoverage = (changes) =>
    setForm((prev) => {
      const payerId = changes.payer_id ?? prev.payer_id
      const others = changes.other_payer_ids ?? prev.other_payer_ids
      const policyFor = (id, current, previousId) =>
        id === previousId ? current : policyFromRegistration(prev.registration, id)
      return {
        ...prev,
        payer_id: payerId,
        other_payer_ids: others,
        billing: {
          ...prev.billing,
          policy: policyFor(payerId, prev.billing.policy, prev.payer_id),
          other_policies: others.map((id) => {
            const at = prev.other_payer_ids.indexOf(id)
            return at >= 0 && id ? prev.billing.other_policies[at] : policyFromRegistration(prev.registration, id)
          }),
        },
      }
    })

  const changePolicy = (index, policy) =>
    setForm((prev) => ({
      ...prev,
      billing:
        index === 0
          ? { ...prev.billing, policy }
          : {
              ...prev.billing,
              other_policies: prev.billing.other_policies.map((p, i) => (i === index - 1 ? policy : p)),
            },
    }))

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
      const { claim } = await createClaim(toRequest(form, lists.procedures, payers))
      // The saved form is now a real claim; it no longer needs keeping
      if (draft.id) {
        await deleteDraft(draft.id).catch(() => {})
        drafts.reload()
      }
      setForm(emptyForm())
      setDraft({ id: null, savedAt: null, saving: false, error: null })
      setOpenClaim({ id: claim.claim_id, justCreated: true })
      reloadDraftClaims()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const reset = () => {
    setForm(emptyForm())
    setOpenClaim(null)
    setError(null)
    setDraft({ id: null, savedAt: null, saving: false, error: null })
  }

  const showDraftClaim = (claim) => {
    setOpenClaim({ id: claim.claim_id, justCreated: false })
    window.scrollTo?.({ top: 0, behavior: 'smooth' })
  }

  const panelOpen = openClaim
    ? { kind: 'claim', id: openClaim.id }
    : draft.id
      ? { kind: 'saved', id: draft.id }
      : null

  return (
    <Page>
      <PageHeader
        title="New claim"
        subtitle="Enter a claim for a registered patient. Save a draft at any point; it’s checked against the rules when you create it."
      />

      {lists.error && <Notice>Could not load the form’s lists — {lists.error}</Notice>}

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_18rem] lg:gap-8">
        <div className="min-w-0">
          {openClaim ? (
            <DraftClaimView
              key={openClaim.id}
              claimId={openClaim.id}
              justCreated={openClaim.justCreated}
              onClose={reset}
              onChanged={reloadDraftClaims}
            />
          ) : (
            <form
              onSubmit={submit}
              aria-busy={submitting}
              className="card relative p-6 sm:p-8"
            >
              <fieldset disabled={submitting} className="space-y-5">
                <FormSection title="Patient" hint="Claims can only be entered for patients registered with the hospital">
                  <PatientPicker patient={form.patient} payers={payers} onChange={choosePatient} />
                  {form.patient && (
                    <>
                      <RegistrationNote registration={form.registration} patient={form.patient} />
                      <PatientDetails details={form.billing} sex={form.patient.gender} onChange={changeBilling} />
                    </>
                  )}
                </FormSection>

                <FormSection title="Coverage" hint="Defaults to the patient’s registered primary payer">
                  <CoverageFields
                    patient={form.patient}
                    payers={payers}
                    payerId={form.payer_id}
                    otherPayerIds={form.other_payer_ids}
                    policies={[form.billing.policy, ...form.billing.other_policies]}
                    onChange={changeCoverage}
                    onPolicyChange={changePolicy}
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

                {form.claim_type === 'Institutional' && (
                  <FormSection title="Institutional details" hint="UB-04 codes for the 837I">
                    <InstitutionalFields
                      details={form.billing.institutional}
                      onChange={(institutional) => changeBilling({ institutional })}
                    />
                  </FormSection>
                )}

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
                    institutional={form.claim_type === 'Institutional'}
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
                <p role="alert" className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
                  Could not create the claim — {error}
                </p>
              )}

              {draft.error && (
                <p role="alert" className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
                  Could not save the draft — {draft.error}
                </p>
              )}

              <div className="mt-6 flex flex-wrap items-center gap-3">
                <button type="submit" disabled={submitting || draft.saving} className="btn-primary">
                  {submitting ? 'Creating & validating…' : 'Create & validate claim'}
                </button>
                {/* Not a submit button: saving skips the form's required fields */}
                <button
                  type="button"
                  onClick={saveAsDraft}
                  disabled={submitting || draft.saving}
                  className="btn-secondary"
                >
                  {draft.saving ? 'Saving…' : 'Save draft'}
                </button>
                {draft.savedAt && !draft.saving && (
                  <span role="status" className="text-sm text-gray-500">
                    Saved at{' '}
                    {draft.savedAt.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })} ·
                    not validated
                  </span>
                )}
              </div>
            </form>
          )}
        </div>

        {/* Above the form on phones, where it would otherwise sit below a long form */}
        <div className="order-first lg:sticky lg:top-6 lg:order-none lg:max-h-[calc(100vh-3rem)] lg:overflow-y-auto">
          <DraftsPanel
            savedDrafts={drafts.data}
            draftClaims={draftClaims.data?.items}
            validations={draftValidations.byId}
            payers={payers}
            open={panelOpen}
            onOpenSaved={openDraft}
            onDeleteSaved={removeDraft}
            onOpenClaim={showDraftClaim}
          />
        </div>
      </div>
    </Page>
  )
}
