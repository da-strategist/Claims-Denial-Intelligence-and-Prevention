import { lazy, Suspense, useEffect, useState } from 'react'
import ErrorBoundary from './components/ErrorBoundary'
import { AuthContext, useAuth, useAuthState } from './hooks/useAuth'
import AuditLog from './pages/AuditLog'
import ClaimsWorkbench from './pages/ClaimsWorkbench'
import JabAudit from './pages/JabAudit'
import Login from './pages/Login'
import NewClaim from './pages/NewClaim'
import RuleManager from './pages/RuleManager'
import { hashPath } from './utils/route'

// Loaded on demand: the chart library is most of its weight
const Dashboard = lazy(() => import('./pages/Dashboard'))

// Hash-based routes, so a refresh keeps the current page without a router library.
// Each needs a permission; pages the user's role lacks are left out of the menu.
const ROUTES = [
  { hash: '#/dashboard', label: 'Dashboard', Page: Dashboard, permission: 'claims:read' },
  { hash: '#/claims', label: 'Claims Workbench', Page: ClaimsWorkbench, permission: 'claims:read' },
  { hash: '#/new-claim', label: 'New Claim', Page: NewClaim, permission: 'claims:write' },
  { hash: '#/rules', label: 'Rule Manager', Page: RuleManager, permission: 'rules:write' },
  { hash: '#/jab', label: 'JAB Audit', Page: JabAudit, permission: 'claims:read' },
  { hash: '#/audit', label: 'Audit Log', Page: AuditLog, permission: 'audit:read' },
]

function useHashRoute(routes) {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const onChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  const route = routes.find((r) => r.hash === hashPath(hash)) ?? routes[0]
  return { route, hash }
}

function App() {
  const auth = useAuthState()
  if (auth.status === 'loading') {
    return <div className="p-6 text-sm text-gray-500">Loading…</div>
  }
  if (auth.status === 'signed-out') {
    return <Login onSignIn={auth.signIn} notice={auth.notice} />
  }
  return (
    <AuthContext.Provider value={auth}>
      <Shell />
    </AuthContext.Provider>
  )
}

const ROLE_LABELS = { analyst: 'Analyst', biller: 'Biller', admin: 'Administrator' }

function UserMenu({ user, onSignOut }) {
  return (
    <div className="ml-auto flex items-center gap-3 text-sm">
      <div className="text-right leading-tight">
        <div className="font-medium text-gray-900">{user.display_name}</div>
        <div className="text-xs text-gray-500">{ROLE_LABELS[user.role] ?? user.role}</div>
      </div>
      <button
        onClick={onSignOut}
        className="rounded-lg border border-gray-200 px-3 py-1.5 font-medium text-gray-700 hover:bg-gray-100"
      >
        Sign out
      </button>
    </div>
  )
}

function Shell() {
  const auth = useAuth()
  const routes = ROUTES.filter((r) => auth.user.permissions.includes(r.permission))
  const { route, hash } = useHashRoute(routes)
  const { Page } = route

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="flex flex-wrap items-center gap-x-8 gap-y-3 border-b border-gray-200 bg-white px-4 py-4 sm:px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-600 text-lg font-bold text-white">
            C
          </div>
          <div>
            <div className="font-semibold text-gray-900">ClaustraRCM</div>
            <div className="text-xs text-gray-500">Claim Validation</div>
          </div>
        </div>
        <nav aria-label="Main" className="flex flex-wrap gap-1">
          {routes.map(({ hash, label }) => (
            <a
              key={hash}
              href={hash}
              aria-current={route.hash === hash ? 'page' : undefined}
              className={`rounded-lg px-3 py-2 text-sm font-medium ${route.hash === hash ? 'bg-red-50 text-red-700' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'}`}
            >
              {label}
            </a>
          ))}
        </nav>
        <UserMenu user={auth.user} onSignOut={auth.signOut} />
      </header>
      <main>
        {/* Keyed by the full hash so a new query (e.g. ?search=) starts the page fresh,
            and leaving a crashed page clears the error */}
        <ErrorBoundary key={hash}>
          <Suspense fallback={<div className="p-4 text-sm text-gray-500 sm:p-6">Loading…</div>}>
            <Page />
          </Suspense>
        </ErrorBoundary>
      </main>
    </div>
  )
}

export default App
