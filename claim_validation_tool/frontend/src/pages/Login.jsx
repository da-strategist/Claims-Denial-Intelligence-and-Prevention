import { useState } from 'react'
import { INPUT_CLASS } from '../constants'

/** Sign-in form. `notice` explains why the user is here (e.g. their session timed out). */
export default function Login({ onSignIn, notice }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await onSignIn(username, password)
    } catch (err) {
      setError(err.message)
      setPassword('')
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <form
        onSubmit={submit}
        aria-label="Sign in"
        className="w-full max-w-sm space-y-4 rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-600 text-lg font-bold text-white">
            C
          </div>
          <div>
            <div className="font-semibold text-gray-900">ClaustraRCM</div>
            <div className="text-xs text-gray-500">Sign in to Claim Validation</div>
          </div>
        </div>
        {notice && !error && (
          <p role="status" className="rounded-lg bg-sky-50 px-3 py-2 text-sm text-sky-800">
            {notice}
          </p>
        )}
        <label className="block space-y-1 text-sm font-medium text-gray-700">
          <span>Username</span>
          <input
            className={INPUT_CLASS}
            autoComplete="username"
            autoFocus
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </label>
        <label className="block space-y-1 text-sm font-medium text-gray-700">
          <span>Password</span>
          <input
            type="password"
            className={INPUT_CLASS}
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && (
          <p role="alert" className="text-sm text-red-700">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-red-600 px-3 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
        >
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
        <p className="text-xs text-gray-500">
          You’re signed out automatically after a period without activity. Accounts are created
          by an administrator.
        </p>
      </form>
    </div>
  )
}
