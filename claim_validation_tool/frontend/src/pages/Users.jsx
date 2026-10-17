import { useId, useState } from 'react'
import Icon from '../components/Icon'
import PageHeader, { Notice, Page } from '../components/PageHeader'
import { FIELD_CLASS, INPUT_CLASS } from '../constants'
import { useApi } from '../hooks/useApi'
import { useAuth } from '../hooks/useAuth'
import { createUser, listUsers, resetUserPassword, updateUser } from '../services/api'

const ROLES = [
  { value: 'analyst', label: 'Analyst', summary: 'Claims and the Overview; patient details hidden' },
  { value: 'biller', label: 'Biller', summary: 'Also patient details; enter, fix, and submit claims' },
  { value: 'admin', label: 'Administrator', summary: 'Also rules, users, and the audit log' },
]
const roleLabel = (value) => ROLES.find((r) => r.value === value)?.label ?? value

// The server's policy, checked as they type so the reasons show before submitting
function passwordProblems(password, confirm) {
  const problems = []
  if (password.length < 12) problems.push('At least 12 characters')
  if (password.toLowerCase() === password || password.toUpperCase() === password)
    problems.push('Upper- and lower-case letters')
  if (/^[a-zA-Z]*$/.test(password)) problems.push('A digit or symbol')
  if (confirm !== password) problems.push('Both passwords match')
  return problems
}

function PasswordFields({ password, confirm, onChange, autoFocus = false }) {
  const base = useId()
  const problems = passwordProblems(password, confirm)
  const rules = ['At least 12 characters', 'Upper- and lower-case letters', 'A digit or symbol', 'Both passwords match']
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <label htmlFor={`${base}-pw`} className="space-y-1 text-sm font-medium text-gray-800">
          <span className="block">Password</span>
          <input
            id={`${base}-pw`}
            type="password"
            autoComplete="new-password"
            autoFocus={autoFocus}
            className={INPUT_CLASS}
            value={password}
            onChange={(e) => onChange({ password: e.target.value, confirm })}
          />
        </label>
        <label htmlFor={`${base}-confirm`} className="space-y-1 text-sm font-medium text-gray-800">
          <span className="block">Repeat password</span>
          <input
            id={`${base}-confirm`}
            type="password"
            autoComplete="new-password"
            className={INPUT_CLASS}
            value={confirm}
            onChange={(e) => onChange({ password, confirm: e.target.value })}
          />
        </label>
      </div>
      <ul aria-label="Password requirements" className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {rules.map((rule) => {
          const met = password !== '' && !problems.includes(rule)
          return (
            <li key={rule} className={`flex items-center gap-1 ${met ? 'text-emerald-700' : 'text-gray-500'}`}>
              <Icon name={met ? 'check' : 'close'} className="h-3.5 w-3.5" strokeWidth={2} />
              {rule}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function AddUser({ onCreated, onCancel }) {
  const base = useId()
  const [form, setForm] = useState({ display_name: '', username: '', role: 'biller' })
  const [secret, setSecret] = useState({ password: '', confirm: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const ready =
    form.display_name.trim() && form.username.trim() && passwordProblems(secret.password, secret.confirm).length === 0

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      onCreated(await createUser({ ...form, password: secret.password }))
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} aria-label="Add user" className="card space-y-5 p-6">
      <h2 className="text-[15px] font-semibold text-gray-900">Add user</h2>
      <div className="grid gap-3 sm:grid-cols-3">
        <label htmlFor={`${base}-name`} className="space-y-1 text-sm font-medium text-gray-800">
          <span className="block">Full name</span>
          <input
            id={`${base}-name`}
            autoFocus
            required
            className={INPUT_CLASS}
            value={form.display_name}
            onChange={(e) => setForm({ ...form, display_name: e.target.value })}
          />
        </label>
        <label htmlFor={`${base}-username`} className="space-y-1 text-sm font-medium text-gray-800">
          <span className="block">Username</span>
          <input
            id={`${base}-username`}
            required
            autoComplete="off"
            pattern="[a-z][a-z0-9._\-]{2,31}"
            title="3–32 lower-case letters, digits, dots, dashes or underscores, starting with a letter"
            className={`${INPUT_CLASS} font-mono`}
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value.toLowerCase().trim() })}
          />
        </label>
        <label htmlFor={`${base}-role`} className="space-y-1 text-sm font-medium text-gray-800">
          <span className="block">Role</span>
          <select
            id={`${base}-role`}
            className={INPUT_CLASS}
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
          >
            {ROLES.map((role) => (
              <option key={role.value} value={role.value}>
                {role.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <PasswordFields password={secret.password} confirm={secret.confirm} onChange={setSecret} />
      {error && <Notice>Could not add the user — {error}</Notice>}
      <div className="flex gap-2">
        <button type="submit" disabled={!ready || busy} className="btn-primary">
          {busy ? 'Adding…' : 'Add user'}
        </button>
        <button type="button" onClick={onCancel} className="btn-secondary">
          Cancel
        </button>
      </div>
    </form>
  )
}

function ResetPassword({ user, onDone, onCancel }) {
  const [secret, setSecret] = useState({ password: '', confirm: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const ready = passwordProblems(secret.password, secret.confirm).length === 0

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await resetUserPassword(user.username, secret.password)
      onDone()
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} aria-label={`New password for ${user.username}`} className="space-y-3 rounded-xl bg-gray-50 p-4">
      <p className="text-sm text-gray-700">
        New password for <strong className="font-medium">{user.display_name}</strong>. They’ll be signed out
        and sign in with it.
      </p>
      <PasswordFields password={secret.password} confirm={secret.confirm} onChange={setSecret} autoFocus />
      {error && <Notice>Could not reset the password — {error}</Notice>}
      <div className="flex gap-2">
        <button type="submit" disabled={!ready || busy} className="btn-primary btn-sm">
          {busy ? 'Saving…' : 'Set password'}
        </button>
        <button type="button" onClick={onCancel} className="btn-secondary btn-sm">
          Cancel
        </button>
      </div>
    </form>
  )
}

function UserRow({ user, isMe, onError, onDone }) {
  const [busy, setBusy] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [confirmingDisable, setConfirmingDisable] = useState(false)

  const save = async (changes, message) => {
    setBusy(true)
    onError(null)
    try {
      await updateUser(user.username, changes)
      onDone(message)
    } catch (err) {
      onError(`${user.display_name}: ${err.message}`)
    } finally {
      setBusy(false)
      setConfirmingDisable(false)
    }
  }

  return (
    <li className={`py-4 ${user.active ? '' : 'opacity-60'}`}>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <div className="min-w-48 flex-1">
          <div className="flex items-center gap-2 text-[15px] font-medium text-gray-900">
            {user.display_name}
            {isMe && <span className="rounded-full bg-accent-soft px-2 py-0.5 text-xs font-medium text-accent">You</span>}
            {!user.active && (
              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">Disabled</span>
            )}
          </div>
          <div className="text-xs text-gray-500">
            <span className="font-mono">{user.username}</span> · password set{' '}
            {new Date(user.password_changed_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}
          </div>
        </div>
        <select
          aria-label={`Role for ${user.username}`}
          className={`${FIELD_CLASS} w-40 py-1.5 text-[13px]`}
          value={user.role}
          disabled={busy || isMe}
          title={isMe ? 'Another administrator has to change your role' : undefined}
          onChange={(e) => save({ role: e.target.value }, `${user.display_name} is now ${roleLabel(e.target.value).toLowerCase()}.`)}
        >
          {ROLES.map((role) => (
            <option key={role.value} value={role.value}>
              {role.label}
            </option>
          ))}
        </select>
        {/* Fixed width so the role selectors line up whatever the buttons say */}
        <div className="flex items-center gap-1 sm:w-60 sm:justify-end">
          <button type="button" className="btn-quiet btn-sm" disabled={busy} onClick={() => setResetting(true)}>
            Reset password
          </button>
          {!isMe &&
            (user.active ? (
              confirmingDisable ? (
                <span className="flex items-center gap-1">
                  <button
                    type="button"
                    className="btn-danger btn-sm"
                    disabled={busy}
                    onClick={() => save({ active: false }, `${user.display_name} is disabled and signed out.`)}
                  >
                    Disable
                  </button>
                  <button type="button" className="btn-secondary btn-sm" onClick={() => setConfirmingDisable(false)}>
                    Keep
                  </button>
                </span>
              ) : (
                <button
                  type="button"
                  className="btn btn-sm text-gray-500 hover:bg-red-50 hover:text-red-700"
                  disabled={busy}
                  onClick={() => setConfirmingDisable(true)}
                  aria-label={`Disable ${user.username}`}
                >
                  Disable
                </button>
              )
            ) : (
              <button
                type="button"
                className="btn-quiet btn-sm"
                disabled={busy}
                onClick={() => save({ active: true }, `${user.display_name} can sign in again.`)}
                aria-label={`Enable ${user.username}`}
              >
                Enable
              </button>
            ))}
        </div>
      </div>
      {resetting && (
        <div className="mt-3">
          <ResetPassword
            user={user}
            onCancel={() => setResetting(false)}
            onDone={() => {
              setResetting(false)
              onDone(`New password set for ${user.display_name}.`)
            }}
          />
        </div>
      )}
    </li>
  )
}

/** Accounts and their roles (administrators). */
export default function Users() {
  const { user: me } = useAuth()
  const { data: users, error, reload } = useApi((options) => listUsers(options))
  const [adding, setAdding] = useState(false)
  const [message, setMessage] = useState(null)
  const [actionError, setActionError] = useState(null)

  const done = (text) => {
    setMessage(text)
    reload()
  }

  return (
    <Page>
      <PageHeader title="Users" subtitle="Who can sign in, and what their role lets them do.">
        {!adding && (
          <button type="button" className="btn-primary" onClick={() => setAdding(true)}>
            <Icon name="plus" className="h-4 w-4" strokeWidth={2} />
            Add user
          </button>
        )}
      </PageHeader>

      {message && <Notice tone="info">{message}</Notice>}
      {(error || actionError) && <Notice>{error ? `Could not load users — ${error}` : actionError}</Notice>}

      {adding && (
        <AddUser
          onCancel={() => setAdding(false)}
          onCreated={(user) => {
            setAdding(false)
            done(
              `${user.display_name} can now sign in as ${user.username} (${roleLabel(user.role).toLowerCase()}). Give them their password in person or by phone, not by email.`,
            )
          }}
        />
      )}

      <section aria-label="Accounts" className="card px-6 py-2">
        {!users && !error && <p className="py-6 text-sm text-gray-500">Loading users…</p>}
        <ul className="divide-y divide-gray-100">
          {(users ?? []).map((user) => (
            <UserRow
              key={user.username}
              user={user}
              isMe={user.username === me.username}
              onError={setActionError}
              onDone={done}
            />
          ))}
        </ul>
      </section>

      <section aria-label="Roles" className="grid gap-3 sm:grid-cols-3">
        {ROLES.map((role) => (
          <div key={role.value} className="rounded-2xl bg-white/60 p-4 ring-1 ring-gray-200/70">
            <div className="text-sm font-semibold text-gray-900">{role.label}</div>
            <div className="text-xs text-gray-500">{role.summary}</div>
          </div>
        ))}
      </section>
    </Page>
  )
}
