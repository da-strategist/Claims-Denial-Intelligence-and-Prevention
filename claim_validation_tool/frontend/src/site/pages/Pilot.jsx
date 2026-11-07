import { useState } from 'react'
import { pilotContactEmail } from '../content'
import { pilotEmail } from '../pilotEmail'

const ORG_TYPES = [
  'Critical Access Hospital',
  'Rural hospital',
  'Community hospital',
  'Health system',
  'Physician practice or clinic',
  'Billing company or RCM vendor',
  'Other',
]

const EMPTY = { name: '', email: '', organization: '', title: '', orgType: '', message: '' }
const LIMITS = { name: 100, email: 200, organization: 150, title: 100, message: 1500 }

function validate(form) {
  const errors = {}
  if (!form.name.trim()) errors.name = 'Enter your full name.'
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) errors.email = 'Enter a work email address, like name@hospital.org.'
  if (!form.organization.trim()) errors.organization = 'Enter your hospital or organization.'
  if (!form.title.trim()) errors.title = 'Enter your job title.'
  if (!form.orgType) errors.orgType = 'Choose your organization type.'
  return errors
}

function Field({ id, label, error, optional, hint, children }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-gray-800">
        {label}
        {optional && <span className="font-normal text-gray-500"> (optional)</span>}
      </label>
      {children}
      {hint && !error && (
        <p id={`${id}-hint`} className="text-xs text-gray-500">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  )
}

/**
 * Pilot interest. Requests go by email: the form checks the details, then opens the visitor's
 * email app with a message addressed to the configured contact, so nothing is stored here and
 * nothing is sent until they send it (VITE_PILOT_CONTACT_EMAIL). Without one it says requests aren't open.
 */
export default function Pilot() {
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [opened, setOpened] = useState(false)
  const contact = pilotContactEmail()
  const configured = Boolean(contact)

  const set = (field) => (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))

  const submit = (event) => {
    event.preventDefault()
    const found = validate(form)
    setErrors(found)
    if (Object.keys(found).length > 0) {
      document.getElementById(`pilot-${Object.keys(found)[0]}`)?.focus()
      return
    }
    window.location.href = pilotEmail(form)
    setOpened(true)
  }

  const describedBy = (field, hint = false) =>
    errors[field] ? `pilot-${field}-error` : hint ? `pilot-${field}-hint` : undefined

  const input = (field, props = {}) => (
    <input
      id={`pilot-${field}`}
      className="field w-full py-2.5"
      value={form[field]}
      onChange={set(field)}
      maxLength={LIMITS[field]}
      aria-invalid={errors[field] ? true : undefined}
      aria-describedby={describedBy(field)}
      disabled={!configured}
      {...props}
    />
  )

  return (
    <div className="mx-auto grid max-w-6xl gap-12 px-5 py-16 sm:px-8 sm:py-24 lg:grid-cols-[1fr_1.15fr]">
      <section aria-labelledby="pilot-heading">
        <div className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">Pilot program</div>
        <h1 id="pilot-heading" className="mt-4 text-4xl font-semibold tracking-tight text-balance text-gray-900 sm:text-5xl sm:leading-[1.08]">
          Interested in Becoming a Pilot Partner?
        </h1>
        <p className="mt-5 text-lg leading-relaxed text-gray-600">
          ClaustraRCM is a working product preparing for its first hospital pilots. Pilot partners validate their own claims with
          us and help shape what it checks next.
        </p>
        <ul className="mt-8 space-y-3 text-[15px] text-gray-700">
          {[
            'Tell us about your organization and how you bill today.',
            'We follow up to talk about your workflow and whether a pilot fits.',
            'Pilot access is by invitation: your administrator gets accounts for your team.',
          ].map((text, index) => (
            <li key={text} className="flex gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold text-accent">
                {index + 1}
              </span>
              {text}
            </li>
          ))}
        </ul>
      </section>

      <section aria-label="Pilot interest form" className="card p-6 shadow-sm sm:p-8">
        {!configured && (
          <p role="status" className="mb-6 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900 ring-1 ring-amber-200">
            Pilot requests aren’t open on this site yet. Please check back soon.
          </p>
        )}
        {opened ? (
          <div role="status" className="space-y-3 py-6 text-center">
            <h2 className="text-xl font-semibold text-gray-900">Your email app should now be open</h2>
            <p className="text-[15px] text-gray-600">
              Your request is ready to send to <span className="font-medium text-gray-900">{contact}</span>. It’s only
              sent once you press Send there.
            </p>
            <p className="text-sm text-gray-500">
              Nothing opened? Email{' '}
              <a className="font-medium text-accent hover:underline" href={`mailto:${contact}`}>
                {contact}
              </a>{' '}
              directly.
            </p>
            <button type="button" className="btn-secondary mt-2" onClick={() => setOpened(false)}>
              Back to the form
            </button>
          </div>
        ) : (
          <form noValidate onSubmit={submit} aria-label="Request a pilot" className="space-y-5">
            <div className="grid gap-5 sm:grid-cols-2">
              <Field id="pilot-name" label="Full name" error={errors.name}>
                {input('name', { autoComplete: 'name', required: true })}
              </Field>
              <Field id="pilot-email" label="Work email" error={errors.email}>
                {input('email', { type: 'email', autoComplete: 'email', required: true })}
              </Field>
              <Field id="pilot-organization" label="Hospital or organization" error={errors.organization}>
                {input('organization', { autoComplete: 'organization', required: true })}
              </Field>
              <Field id="pilot-title" label="Job title" error={errors.title}>
                {input('title', { autoComplete: 'organization-title', required: true })}
              </Field>
            </div>
            <Field id="pilot-orgType" label="Organization type" error={errors.orgType}>
              <select
                id="pilot-orgType"
                className="field w-full py-2.5"
                value={form.orgType}
                onChange={set('orgType')}
                aria-invalid={errors.orgType ? true : undefined}
                aria-describedby={describedBy('orgType')}
                disabled={!configured}
                required
              >
                <option value="">Choose…</option>
                {ORG_TYPES.map((type) => (
                  <option key={type}>{type}</option>
                ))}
              </select>
            </Field>
            <Field
              id="pilot-message"
              label="Message"
              optional
              hint="Please don’t include any patient information."
              error={errors.message}
            >
              <textarea
                id="pilot-message"
                rows={4}
                className="field w-full py-2.5"
                value={form.message}
                onChange={set('message')}
                maxLength={LIMITS.message}
                aria-describedby={describedBy('message', true)}
                disabled={!configured}
              />
            </Field>
            <button type="submit" className="btn-primary w-full py-3 text-base" disabled={!configured}>
              Continue in your email app
            </button>
            <p className="text-center text-xs leading-relaxed text-gray-500">
              This opens your email app with your request filled in. Nothing is stored on this site, and nothing is sent until you
              send the email.
            </p>
          </form>
        )}
      </section>
    </div>
  )
}
