import { useEffect, useState } from 'react'
import Icon from '../components/Icon'
import Logo from '../components/Logo'
import { INPUT_CLASS } from '../constants'
import { getHealth } from '../services/api'

const PROMISE = [
  ['Load', 'Claims from your systems, a file, or the claim form'],
  ['Validate & Correct', 'Errors explained, with a suggested fix to confirm'],
  ['Send', 'Clean claims ready for your submission workflow'],
]

/** Sign-in, split screen: the product's promise on one side, the form on the other.
 * `notice` explains why the user is here (e.g. their session timed out). Accounts are
 * created by an administrator; there's no self-registration. */
export default function Login({ onSignIn, notice }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [visible, setVisible] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  // A demo server says so; the pilot and production servers don't
  const [demo, setDemo] = useState(false)
  useEffect(() => {
    getHealth()
      .then((health) => setDemo(Boolean(health?.demo)))
      .catch(() => {})
  }, [])

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
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <aside className="relative hidden overflow-hidden bg-navy p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_50%_at_30%_100%,rgba(10,108,224,0.35),transparent)]"
        />
        <a href="/" className="relative flex w-fit items-center gap-2.5 rounded-lg">
          <Logo />
          <span className="text-[17px] font-semibold tracking-tight">ClaustraRCM</span>
        </a>
        <div className="relative max-w-md">
          <h2 className="text-4xl leading-[1.1] font-semibold tracking-tight text-balance">Better claims start before submission.</h2>
          <ol className="mt-10 space-y-4">
            {PROMISE.map(([step, text], index) => (
              <li key={step} className="flex gap-4 rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white/10 font-mono text-xs text-sky-300">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <div>
                  <div className="font-semibold">{step}</div>
                  <div className="text-sm text-slate-300">{text}</div>
                </div>
              </li>
            ))}
          </ol>
        </div>
        <p className="relative text-xs text-slate-400">
          Sign-in is for invited users.{demo && ' Demonstrations use synthetic data.'}
        </p>
      </aside>

      <div className="flex flex-col px-4 py-10 sm:px-8">
        <a href="/" className="flex w-fit items-center gap-1.5 rounded-lg text-sm text-gray-500 hover:text-gray-900">
          <Icon name="back" className="h-4 w-4" /> ClaustraRCM home
        </a>
        <div className="flex flex-1 items-center justify-center py-10">
          <div className="w-full max-w-sm">
            <div className="mb-8">
              <div className="lg:hidden">
                <Logo size="h-11 w-11 text-lg rounded-2xl" />
              </div>
              <h1 className="mt-5 text-3xl font-semibold tracking-tight text-gray-900 lg:mt-0">Sign in to ClaustraRCM</h1>
              <p className="mt-1.5 text-[15px] text-gray-500">Catch claim problems before payers do.</p>
            </div>
            <form onSubmit={submit} aria-label="Sign in" className="space-y-4">
              {notice && !error && (
                <p role="status" className="rounded-xl bg-accent-soft px-3 py-2 text-sm text-gray-800">
                  {notice}
                </p>
              )}
              <label className="block space-y-1.5 text-sm font-medium text-gray-700">
                <span>Username</span>
                <input
                  className={`${INPUT_CLASS} py-2.5`}
                  autoComplete="username"
                  autoFocus
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </label>
              <div className="space-y-1.5">
                <label htmlFor="login-password" className="block text-sm font-medium text-gray-700">
                  Password
                </label>
                <div className="relative">
                  <input
                    id="login-password"
                    type={visible ? 'text' : 'password'}
                    className={`${INPUT_CLASS} py-2.5 pr-16`}
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    onClick={() => setVisible((v) => !v)}
                    aria-pressed={visible}
                    aria-controls="login-password"
                    className="absolute inset-y-1 right-1 rounded-lg px-2.5 text-xs font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-900"
                  >
                    {visible ? 'Hide' : 'Show'}
                    <span className="sr-only"> password</span>
                  </button>
                </div>
              </div>
              {error && (
                <p role="alert" className="text-sm text-red-700">
                  {error}
                </p>
              )}
              <button type="submit" disabled={busy} className="btn-primary w-full py-3 text-[15px]">
                {busy ? 'Signing in…' : 'Sign in'}
              </button>
            </form>
            <div className="mt-8 space-y-2 text-sm leading-relaxed text-gray-500">
              <p>Forgot your password? Your administrator can reset it.</p>
              <p>
                No account yet? Access is by invitation during the pilot.{' '}
                <a href="/pilot" className="font-medium text-accent hover:underline">
                  Request a pilot
                </a>
              </p>
              <p className="text-xs text-gray-400">You’re signed out automatically after a period without activity.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
