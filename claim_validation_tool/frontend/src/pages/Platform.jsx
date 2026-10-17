import { useId, useState } from 'react'
import EmergencyAccessList from '../components/EmergencyAccessList'
import Icon from '../components/Icon'
import PageHeader, { Notice, Page } from '../components/PageHeader'
import PasswordFields from '../components/PasswordFields'
import { INPUT_CLASS } from '../constants'
import { useApi } from '../hooks/useApi'
import { useAuth } from '../hooks/useAuth'
import {
  addOrganisationAdmin,
  createOrganisation,
  endEmergencyAccess,
  listEmergencyAccess,
  listOrganisations,
  listPlatformAudit,
  setOrganisationActive,
  startEmergencyAccess,
} from '../services/api'
import { passwordProblems } from '../utils/password'

const DURATIONS = [15, 30, 60, 120, 240]
const when = (iso) =>
  new Date(iso).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })

function Field({ label, children }) {
  const id = useId()
  return (
    <label htmlFor={id} className="space-y-1 text-sm font-medium text-gray-800">
      <span className="block">{label}</span>
      {children(id)}
    </label>
  )
}

function NewOrganisation({ onDone, onCancel }) {
  const [form, setForm] = useState({ id: '', name: '' })
  const [error, setError] = useState(null)
  return (
    <form
      aria-label="New organisation"
      className="card space-y-4 p-6"
      onSubmit={async (e) => {
        e.preventDefault()
        setError(null)
        try {
          const org = await createOrganisation(form)
          onDone(`${org.name} is ready. Add its first administrator, then load its patients, providers, and claims.`)
        } catch (err) {
          setError(err.message)
        }
      }}
    >
      <h2 className="text-[15px] font-semibold text-gray-900">New organisation</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Name">
          {(id) => <input id={id} required className={INPUT_CLASS} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />}
        </Field>
        <Field label="ID (short, lower case)">
          {(id) => (
            <input
              id={id}
              required
              pattern="[a-z][a-z0-9\-]{1,31}"
              title="2–32 lower-case letters, digits, or dashes, starting with a letter"
              className={`${INPUT_CLASS} font-mono`}
              value={form.id}
              onChange={(e) => setForm({ ...form, id: e.target.value.toLowerCase().trim() })}
            />
          )}
        </Field>
      </div>
      <p className="text-xs text-gray-500">
        It starts with the shared code sets and no patients, providers, or claims of its own.
      </p>
      {error && <Notice>Could not create it — {error}</Notice>}
      <div className="flex gap-2">
        <button type="submit" className="btn-primary">Create organisation</button>
        <button type="button" className="btn-secondary" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  )
}

function AddAdmin({ org, onDone, onCancel }) {
  const [form, setForm] = useState({ display_name: '', username: '' })
  const [secret, setSecret] = useState({ password: '', confirm: '' })
  const [error, setError] = useState(null)
  const ready = form.display_name && form.username && passwordProblems(secret.password, secret.confirm).length === 0
  return (
    <form
      aria-label={`Add administrator to ${org.name}`}
      className="space-y-3 rounded-xl bg-gray-50 p-4"
      onSubmit={async (e) => {
        e.preventDefault()
        setError(null)
        try {
          const user = await addOrganisationAdmin(org.id, { ...form, password: secret.password })
          onDone(`${user.display_name} can now sign in as ${user.username} and manage ${org.name}.`)
        } catch (err) {
          setError(err.message)
        }
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Full name">
          {(id) => <input id={id} required className={INPUT_CLASS} value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} />}
        </Field>
        <Field label="Username">
          {(id) => (
            <input
              id={id}
              required
              autoComplete="off"
              className={`${INPUT_CLASS} font-mono`}
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value.toLowerCase().trim() })}
            />
          )}
        </Field>
      </div>
      <PasswordFields password={secret.password} confirm={secret.confirm} onChange={setSecret} />
      {error && <Notice>Could not add them — {error}</Notice>}
      <div className="flex gap-2">
        <button type="submit" disabled={!ready} className="btn-primary btn-sm">Add administrator</button>
        <button type="button" className="btn-secondary btn-sm" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  )
}

function EmergencyForm({ org, onStarted, onCancel }) {
  const [reason, setReason] = useState('')
  const [minutes, setMinutes] = useState(60)
  const [error, setError] = useState(null)
  return (
    <form
      aria-label={`Emergency access to ${org.name}`}
      className="space-y-3 rounded-xl bg-red-50/60 p-4 ring-1 ring-red-100"
      onSubmit={async (e) => {
        e.preventDefault()
        setError(null)
        try {
          await startEmergencyAccess(org.id, reason, Number(minutes))
          onStarted()
        } catch (err) {
          setError(err.message)
        }
      }}
    >
      <p className="text-sm text-red-900">
        Emergency access lets you <strong className="font-medium">look</strong> at {org.name}’s claims and
        patients, read-only, for a limited time. {org.name}’s administrators see it in their audit log with your
        reason, and can end it.
      </p>
      <Field label="Reason (the organisation will see this)">
        {(id) => (
          <textarea
            id={id}
            required
            minLength={20}
            maxLength={500}
            rows={2}
            className={INPUT_CLASS}
            placeholder="e.g. Ticket 4471: claims page fails to load for the billing team"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        )}
      </Field>
      <Field label="For">
        {(id) => (
          <select id={id} className={`${INPUT_CLASS} sm:w-48`} value={minutes} onChange={(e) => setMinutes(e.target.value)}>
            {DURATIONS.map((m) => (
              <option key={m} value={m}>
                {m < 60 ? `${m} minutes` : `${m / 60} hour${m > 60 ? 's' : ''}`}
              </option>
            ))}
          </select>
        )}
      </Field>
      {error && <Notice>Could not start it — {error}</Notice>}
      <div className="flex gap-2">
        <button type="submit" disabled={reason.trim().length < 20} className="btn-danger btn-sm">
          Start read-only access
        </button>
        <button type="button" className="btn-secondary btn-sm" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  )
}

function OrganisationRow({ org, onDone, onError, onStarted }) {
  const [open, setOpen] = useState(null) // 'admin' | 'emergency' | 'suspend'
  const suspended = org.status === 'suspended'
  return (
    <li className="py-4">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        <div className="min-w-48 flex-1">
          <div className="flex items-center gap-2 text-[15px] font-medium text-gray-900">
            {org.name}
            {suspended && <span className="rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700">Suspended</span>}
          </div>
          <div className="text-xs text-gray-500">
            <span className="font-mono">{org.id}</span> · {org.accounts} account{org.accounts === 1 ? '' : 's'} ·{' '}
            {org.active_admins ? `${org.active_admins} active admin${org.active_admins === 1 ? '' : 's'}` : (
              <span className="text-amber-700">no active administrator</span>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1">
          <button type="button" className="btn-quiet btn-sm" onClick={() => setOpen('admin')}>Add admin</button>
          {!suspended && (
            <button type="button" className="btn-quiet btn-sm" onClick={() => setOpen('emergency')}>
              Emergency access
            </button>
          )}
          {open === 'suspend' ? (
            <span className="flex items-center gap-1">
              <button
                type="button"
                className="btn-danger btn-sm"
                onClick={async () => {
                  try {
                    await setOrganisationActive(org.id, false)
                    onDone(`${org.name} is suspended; its users were signed out.`)
                  } catch (err) {
                    onError(err.message)
                  }
                  setOpen(null)
                }}
              >
                Suspend
              </button>
              <button type="button" className="btn-secondary btn-sm" onClick={() => setOpen(null)}>Keep</button>
            </span>
          ) : suspended ? (
            <button
              type="button"
              className="btn-quiet btn-sm"
              onClick={async () => {
                await setOrganisationActive(org.id, true)
                onDone(`${org.name} is active again.`)
              }}
            >
              Reactivate
            </button>
          ) : (
            <button
              type="button"
              className="btn btn-sm text-gray-500 hover:bg-red-50 hover:text-red-700"
              aria-label={`Suspend ${org.name}`}
              onClick={() => setOpen('suspend')}
            >
              Suspend
            </button>
          )}
        </div>
      </div>
      {open === 'admin' && (
        <div className="mt-3">
          <AddAdmin org={org} onCancel={() => setOpen(null)} onDone={(m) => { setOpen(null); onDone(m) }} />
        </div>
      )}
      {open === 'emergency' && (
        <div className="mt-3">
          <EmergencyForm org={org} onCancel={() => setOpen(null)} onStarted={onStarted} />
        </div>
      )}
    </li>
  )
}

/** Organisations, their first administrators, and emergency access (platform accounts). */
export default function Platform() {
  const auth = useAuth()
  const orgs = useApi((options) => listOrganisations(options))
  const grants = useApi((options) => listEmergencyAccess(options))
  const activity = useApi((options) => listPlatformAudit(options))
  const [creating, setCreating] = useState(false)
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)
  const orgNames = Object.fromEntries((orgs.data ?? []).map((o) => [o.id, o.name]))

  const done = (text) => {
    setMessage(text)
    setError(null)
    orgs.reload()
    grants.reload()
    activity.reload()
  }
  // Starting emergency access changes what this account sees: reload who it is, then
  // open the organisation's Overview
  const switchAccess = async () => {
    const user = await auth.refresh()
    window.location.hash = user.emergency ? '#/dashboard' : '#/platform'
  }

  return (
    <Page>
      <PageHeader title="Platform" subtitle="Organisations using this service. You don’t see their patients or claims.">
        {!creating && (
          <button type="button" className="btn-primary" onClick={() => setCreating(true)}>
            <Icon name="plus" className="h-4 w-4" strokeWidth={2} />
            New organisation
          </button>
        )}
      </PageHeader>
      {message && <Notice tone="info">{message}</Notice>}
      {(error || orgs.error) && <Notice>{error ?? `Could not load organisations — ${orgs.error}`}</Notice>}
      {creating && <NewOrganisation onCancel={() => setCreating(false)} onDone={(m) => { setCreating(false); done(m) }} />}

      <section aria-label="Organisations" className="card px-6 py-2">
        <ul className="divide-y divide-gray-100">
          {(orgs.data ?? []).map((org) => (
            <OrganisationRow key={org.id} org={org} onDone={done} onError={setError} onStarted={switchAccess} />
          ))}
        </ul>
      </section>

      <section aria-labelledby="emergency-title" className="card space-y-1 px-6 py-4">
        <h2 id="emergency-title" className="text-[15px] font-semibold text-gray-900">Emergency access</h2>
        <EmergencyAccessList
          grants={grants.data}
          orgNames={orgNames}
          onEnd={async (grant) => {
            await endEmergencyAccess(grant.id)
            done('Emergency access ended.')
            await auth.refresh()
          }}
        />
      </section>

      <section aria-labelledby="activity-title" className="card space-y-2 px-6 py-4">
        <h2 id="activity-title" className="text-[15px] font-semibold text-gray-900">Platform activity</h2>
        <p className="text-xs text-gray-500">Platform accounts’ requests and sign-ins with unknown usernames.</p>
        <ul className="divide-y divide-gray-100 text-sm">
          {(activity.data ?? []).slice(0, 15).map((event) => (
            <li key={event.seq} className="flex flex-wrap gap-x-4 py-2">
              <span className="w-36 text-gray-500">{when(event.at)}</span>
              <span className="w-28 text-gray-700">{event.username ?? '—'}</span>
              <span className="font-mono text-xs text-gray-800">{event.action}</span>
              <span className="ml-auto text-xs text-gray-500">{event.status_code}</span>
            </li>
          ))}
        </ul>
      </section>
    </Page>
  )
}
