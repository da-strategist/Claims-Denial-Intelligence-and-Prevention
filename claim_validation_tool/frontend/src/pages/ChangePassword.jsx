import { useId, useState } from 'react'
import Logo from '../components/Logo'
import PasswordFields from '../components/PasswordFields'
import { INPUT_CLASS } from '../constants'
import { useAuth } from '../hooks/useAuth'
import { passwordProblems } from '../utils/password'

/**
 * Choose your own password. `required`: someone else set the current one (a new account or a
 * reset), and nothing else opens until it's replaced. Otherwise it's opened from the account
 * menu and `onClose` goes back.
 */
export default function ChangePassword({ required = false, onClose }) {
  const auth = useAuth()
  const currentId = useId()
  const [current, setCurrent] = useState('')
  const [secret, setSecret] = useState({ password: '', confirm: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)
  const ready = current !== '' && passwordProblems(secret.password, secret.confirm).length === 0

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await auth.updatePassword(current, secret.password)
      setDone(true)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  if (done && !required) {
    return (
      <div className="mx-auto max-w-md space-y-4 p-10">
        <p role="status" className="rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          Your password is changed. Any other sessions were signed out.
        </p>
        <button type="button" className="btn-secondary" onClick={onClose}>
          Back
        </button>
      </div>
    )
  }

  const form = (
    <form onSubmit={submit} aria-label="Choose a new password" className="space-y-4">
      <div className="space-y-1.5">
        <label htmlFor={currentId} className="block text-sm font-medium text-gray-800">
          {required ? 'Password you were given' : 'Current password'}
        </label>
        <input
          id={currentId}
          type="password"
          autoComplete="current-password"
          autoFocus
          required
          className={INPUT_CLASS}
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
        />
      </div>
      <PasswordFields password={secret.password} confirm={secret.confirm} onChange={setSecret} />
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button type="submit" disabled={!ready || busy} className="btn-primary">
          {busy ? 'Saving…' : 'Save new password'}
        </button>
        {required ? (
          <button type="button" className="btn-secondary" onClick={auth.signOut}>
            Sign out
          </button>
        ) : (
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
        )}
      </div>
    </form>
  )

  if (!required) {
    return (
      <div className="mx-auto max-w-xl space-y-6 p-6 sm:p-10">
        <h1 className="text-2xl font-semibold tracking-tight text-gray-900">Change your password</h1>
        {form}
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-lg space-y-6">
        <Logo size="h-11 w-11 text-lg rounded-2xl" />
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-gray-900">Choose your own password</h1>
          <p className="mt-1.5 text-[15px] text-gray-500">
            Welcome, {auth.user.display_name}. The password you signed in with was set for you, so it’s only
            temporary. Choose one that only you know to continue.
          </p>
        </div>
        {form}
      </div>
    </div>
  )
}
