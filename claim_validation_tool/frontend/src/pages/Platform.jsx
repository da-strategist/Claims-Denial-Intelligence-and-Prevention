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
  approvePilotRequest,
  createOrganisation,
  declinePilotRequest,
  deleteOrganisation,
  endEmergencyAccess,
  listEmergencyAccess,
  listOrganisations,
  listPilotRequests,
  listPlatformAudit,
  recordBaa,
  setOrganisationActive,
  startEmergencyAccess,
} from '../services/api'
import { passwordProblems } from '../utils/password'

const DURATIONS = [15, 30, 60, 120, 240]
const day = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
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

// Suggestions from a pilot request, to check and change before approving
const orgIdFrom = (name) =>
  name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^[^a-z]+/, '')
    .slice(0, 32)
    .replace(/-+$/, '')
const usernameFrom = (email) =>
  email
    .split('@')[0]
    .toLowerCase()
    .replace(/[^a-z0-9._-]/g, '')
    .replace(/^[^a-z]+/, '')
    .slice(0, 32)

/** New organisation with its first administrator; `request` approves a pilot request with it. */
function NewOrganisation({ onDone, onCancel, request = null }) {
  const [form, setForm] = useState(
    request ? { id: orgIdFrom(request.organization), name: request.organization } : { id: '', name: '' },
  )
  const [admin, setAdmin] = useState(
    request ? { display_name: request.name, username: usernameFrom(request.email) } : { display_name: '', username: '' },
  )
  const [secret, setSecret] = useState({ password: '', confirm: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const ready =
    form.id && form.name && admin.display_name && admin.username &&
    passwordProblems(secret.password, secret.confirm).length === 0
  return (
    <form
      aria-label="New organisation"
      className="card space-y-4 p-6"
      onSubmit={async (e) => {
        e.preventDefault()
        setError(null)
        setBusy(true)
        try {
          const body = { ...form, admin: { ...admin, password: secret.password } }
          const org = request ? await approvePilotRequest(request.id, body) : await createOrganisation(body)
          onDone(
            `${org.name} is ready, and ${admin.display_name} can sign in as ${admin.username} to manage it. ` +
              'Give them the password in person or by phone, not by email; it’s temporary, and they choose their own when they first sign in. Next, load its patients, providers, and claims.',
          )
        } catch (err) {
          setError(err.message)
          setBusy(false)
        }
      }}
    >
      <h2 className="text-[15px] font-semibold text-gray-900">
        {request ? `Approve ${request.organization}` : 'New organisation'}
      </h2>
      {request && (
        <p className="text-xs text-gray-500">
          Filled in from the request: check the ID and username before creating it. Approving creates the organisation
          and its first administrator, then marks the request approved. Nothing is emailed to {request.name}: contact them
          at {request.email} yourself.
        </p>
      )}
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

      <fieldset className="space-y-3 border-t border-gray-100 pt-4">
        <legend className="text-[15px] font-semibold text-gray-900">First administrator</legend>
        <p className="text-xs text-gray-500">
          They manage the organisation’s own accounts, rules and settings. Created together with the organisation. The password you set is temporary: they choose their own when they first sign in.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Full name">
            {(id) => (
              <input
                id={id}
                required
                className={INPUT_CLASS}
                value={admin.display_name}
                onChange={(e) => setAdmin({ ...admin, display_name: e.target.value })}
              />
            )}
          </Field>
          <Field label="Username">
            {(id) => (
              <input
                id={id}
                required
                autoComplete="off"
                className={`${INPUT_CLASS} font-mono`}
                value={admin.username}
                onChange={(e) => setAdmin({ ...admin, username: e.target.value.toLowerCase().trim() })}
              />
            )}
          </Field>
        </div>
        <PasswordFields password={secret.password} confirm={secret.confirm} onChange={setSecret} />
      </fieldset>

      {error && <Notice>Could not create it — {error}</Notice>}
      <div className="flex gap-2">
        <button type="submit" disabled={!ready || busy} className="btn-primary">
          {busy ? 'Creating…' : request ? 'Approve and create' : 'Create organisation'}
        </button>
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
          onDone(`${user.display_name} can now sign in as ${user.username} and manage ${org.name}. Give them the password in person or by phone, not by email; it’s temporary, and they choose their own when they first sign in.`)
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

function BaaForm({ org, onDone, onCancel }) {
  const [form, setForm] = useState({ signed_on: '', reference: '', signatory: '' })
  const [error, setError] = useState(null)
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })
  return (
    <form
      aria-label={`Business associate agreement for ${org.name}`}
      className="space-y-3 rounded-xl bg-gray-50 p-4"
      onSubmit={async (e) => {
        e.preventDefault()
        setError(null)
        try {
          await recordBaa(org.id, form)
          onDone(`${org.name}’s business associate agreement is on record.`)
        } catch (err) {
          setError(err.message)
        }
      }}
    >
      <p className="text-sm text-gray-600">
        Record the signed agreement before loading real patient data. In production, an organisation without one
        can’t sign in.
      </p>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Signed on">
          {(id) => <input id={id} type="date" required className={INPUT_CLASS} value={form.signed_on} onChange={set('signed_on')} />}
        </Field>
        <Field label="Reference">
          {(id) => <input id={id} required maxLength={120} placeholder="e.g. BAA-2026-014" className={INPUT_CLASS} value={form.reference} onChange={set('reference')} />}
        </Field>
        <Field label="Signed by (for the organisation)">
          {(id) => <input id={id} required maxLength={120} className={INPUT_CLASS} value={form.signatory} onChange={set('signatory')} />}
        </Field>
      </div>
      {error && <Notice>Could not record it — {error}</Notice>}
      <div className="flex gap-2">
        <button type="submit" className="btn-primary btn-sm">Record agreement</button>
        <button type="button" className="btn-secondary btn-sm" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  )
}

function DeleteForm({ org, onDone, onCancel }) {
  const [typed, setTyped] = useState('')
  const [error, setError] = useState(null)
  return (
    <form
      aria-label={`Delete ${org.name}`}
      className="space-y-3 rounded-xl bg-red-50/60 p-4 ring-1 ring-red-100"
      onSubmit={async (e) => {
        e.preventDefault()
        setError(null)
        try {
          const result = await deleteOrganisation(org.id, typed)
          onDone(`${org.name} was deleted: ${result.done.join('; ')}.`)
        } catch (err) {
          setError(err.message)
        }
      }}
    >
      <p className="text-sm text-red-900">
        This destroys {org.name}’s encryption key, deletes its data and its {org.accounts} account
        {org.accounts === 1 ? '' : 's'}, and can’t be undone. Copies in backups become unreadable. If it’s leaving,
        have one of its administrators export its data first.
      </p>
      <Field label={`Type ${org.id} to confirm`}>
        {(id) => (
          <input
            id={id}
            autoComplete="off"
            className={`${INPUT_CLASS} font-mono sm:w-64`}
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
          />
        )}
      </Field>
      {error && <Notice>Could not delete it — {error}</Notice>}
      <div className="flex gap-2">
        <button type="submit" disabled={typed.trim() !== org.id} className="btn-danger btn-sm">Delete for good</button>
        <button type="button" className="btn-secondary btn-sm" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  )
}

function DeletedRow({ org }) {
  return (
    <li className="py-4 text-sm text-gray-500">
      <span className="font-medium text-gray-700">{org.name}</span> · <span className="font-mono">{org.id}</span> ·
      deleted {when(org.deleted_at)}
    </li>
  )
}

function OrganisationRow({ org, onDone, onError, onStarted }) {
  const [open, setOpen] = useState(null) // 'admin' | 'emergency' | 'suspend' | 'baa' | 'delete'
  const suspended = org.status === 'suspended'
  if (org.status === 'deleted') return <DeletedRow org={org} />
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
          <div className="text-xs text-gray-500">
            {org.baa ? (
              `BAA ${org.baa.reference}, signed ${day(org.baa.signed_on)} by ${org.baa.signatory}`
            ) : (
              <span className="text-amber-700">No business associate agreement on record</span>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1">
          <button type="button" className="btn-quiet btn-sm" onClick={() => setOpen('admin')}>Add admin</button>
          <button type="button" className="btn-quiet btn-sm" aria-label={`Record BAA for ${org.name}`} onClick={() => setOpen('baa')}>
            {org.baa ? 'Update BAA' : 'Record BAA'}
          </button>
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
            <>
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
              <button
                type="button"
                className="btn btn-sm text-gray-500 hover:bg-red-50 hover:text-red-700"
                aria-label={`Delete ${org.name}`}
                onClick={() => setOpen('delete')}
              >
                Delete…
              </button>
            </>
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
      {open === 'baa' && (
        <div className="mt-3">
          <BaaForm org={org} onCancel={() => setOpen(null)} onDone={(m) => { setOpen(null); onDone(m) }} />
        </div>
      )}
      {open === 'delete' && (
        <div className="mt-3">
          <DeleteForm org={org} onCancel={() => setOpen(null)} onDone={(m) => { setOpen(null); onDone(m) }} />
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
const STATUS_TONE = {
  pending: 'bg-amber-50 text-amber-900 ring-amber-200',
  approved: 'bg-emerald-50 text-emerald-900 ring-emerald-200',
  declined: 'bg-gray-100 text-gray-700 ring-gray-200',
}

function DeclineForm({ request, onDone, onCancel }) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState(null)
  return (
    <form
      aria-label={`Decline ${request.organization}`}
      className="mt-3 space-y-3 rounded-xl bg-gray-50 p-4"
      onSubmit={async (e) => {
        e.preventDefault()
        try {
          await declinePilotRequest(request.id, reason.trim())
          onDone(`${request.organization}’s request was declined. Let ${request.name} know yourself.`)
        } catch (err) {
          setError(err.message)
        }
      }}
    >
      <Field label="Reason (kept for the record)">
        {(id) => (
          <input
            id={id}
            required
            minLength={3}
            maxLength={500}
            className={INPUT_CLASS}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        )}
      </Field>
      {error && <Notice>Could not decline it — {error}</Notice>}
      <div className="flex gap-2">
        <button type="submit" disabled={reason.trim().length < 3} className="btn-danger btn-sm">Decline request</button>
        <button type="button" className="btn-secondary btn-sm" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  )
}

function PilotRequestRow({ request, open, onOpen, onDone }) {
  const decided = request.status !== 'pending'
  return (
    <li className="py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 text-sm">
          <p className="font-medium text-gray-900">
            {request.organization}
            <span className={`ml-2 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${STATUS_TONE[request.status]}`}>
              {request.status[0].toUpperCase() + request.status.slice(1)}
            </span>
          </p>
          <p className="text-xs text-gray-500">
            {request.name} · {request.title} · {request.email} · {request.org_type} · {when(request.received_at)}
          </p>
          {request.message && <p className="mt-1 max-w-2xl text-sm whitespace-pre-line text-gray-700">{request.message}</p>}
          {decided && (
            <p className="mt-1 text-xs text-gray-500">
              {request.status === 'approved'
                ? `Approved by ${request.decided_by}: ${request.organisation_id}`
                : `Declined by ${request.decided_by}: “${request.decline_reason}”`}{' '}
              · {when(request.decided_at)}
            </p>
          )}
        </div>
        {!decided && !open && (
          <div className="flex gap-2">
            <button type="button" className="btn-primary btn-sm" onClick={() => onOpen('approve')}>
              Approve
            </button>
            <button type="button" className="btn-secondary btn-sm" onClick={() => onOpen('decline')}>
              Decline
            </button>
          </div>
        )}
      </div>
      {open === 'approve' && (
        <div className="mt-3">
          <NewOrganisation request={request} onCancel={() => onOpen(null)} onDone={onDone} />
        </div>
      )}
      {open === 'decline' && <DeclineForm request={request} onCancel={() => onOpen(null)} onDone={onDone} />}
    </li>
  )
}

function PilotRequests({ requests, error, onDone }) {
  const [open, setOpen] = useState(null) // { id, action }
  const [showDecided, setShowDecided] = useState(false)
  const pending = (requests ?? []).filter((r) => r.status === 'pending')
  const decided = (requests ?? []).filter((r) => r.status !== 'pending')
  const row = (request) => (
    <PilotRequestRow
      key={request.id}
      request={request}
      open={open?.id === request.id ? open.action : null}
      onOpen={(action) => setOpen(action ? { id: request.id, action } : null)}
      onDone={(message) => {
        setOpen(null)
        onDone(message)
      }}
    />
  )
  return (
    <section aria-labelledby="pilot-requests-title" className="card space-y-1 px-6 py-4">
      <h2 id="pilot-requests-title" className="text-[15px] font-semibold text-gray-900">
        Pilot requests{pending.length > 0 && ` · ${pending.length} pending`}
      </h2>
      <p className="text-xs text-gray-500">
        From the website’s pilot form. Approving creates the organisation; its BAA must still be recorded before it loads
        real claims. Decided requests are deleted after 12 months.
      </p>
      {error && <Notice>Could not load pilot requests — {error}</Notice>}
      {requests && pending.length === 0 && <p className="py-2 text-sm text-gray-500">No requests waiting.</p>}
      <ul className="divide-y divide-gray-100">{pending.map(row)}</ul>
      {decided.length > 0 && (
        <>
          <button type="button" className="text-sm font-medium text-accent hover:underline" onClick={() => setShowDecided((v) => !v)}>
            {showDecided ? 'Hide decided requests' : `Show decided requests (${decided.length})`}
          </button>
          {showDecided && <ul className="divide-y divide-gray-100">{decided.map(row)}</ul>}
        </>
      )}
    </section>
  )
}

export default function Platform() {
  const auth = useAuth()
  const orgs = useApi((options) => listOrganisations(options))
  const grants = useApi((options) => listEmergencyAccess(options))
  const activity = useApi((options) => listPlatformAudit(options))
  const pilots = useApi((options) => listPilotRequests(options))
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
    pilots.reload()
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

      <PilotRequests requests={pilots.data} error={pilots.error} onDone={done} />

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
