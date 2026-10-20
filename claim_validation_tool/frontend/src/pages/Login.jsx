import { useState } from 'react'
import Logo from '../components/Logo'
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
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <Logo size="h-12 w-12 text-xl rounded-2xl" />
          <h1 className="mt-5 text-2xl font-semibold tracking-tight text-gray-900">
            Sign in to ClaustraRCM
          </h1>
          <p className="mt-1 text-[15px] text-gray-500">Catch claim problems before payers do.</p>
        </div>
        <form onSubmit={submit} aria-label="Sign in" className="card space-y-4 p-6 shadow-sm">
          {notice && !error && (
            <p role="status" className="rounded-xl bg-accent-soft px-3 py-2 text-sm text-gray-800">
              {notice}
            </p>
          )}
          <label className="block space-y-1.5 text-sm font-medium text-gray-700">
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
          <label className="block space-y-1.5 text-sm font-medium text-gray-700">
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
          <button type="submit" disabled={busy} className="btn-primary w-full py-2.5">
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <p className="mt-6 text-center text-xs leading-relaxed text-gray-500">
          You’re signed out automatically after a period without activity.
          <br />
          Accounts are created by an administrator.
        </p>
      </div>
    </div>
  )
}
