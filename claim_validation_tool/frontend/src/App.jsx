import { lazy, Suspense, useEffect, useState } from 'react'
import ErrorBoundary from './components/ErrorBoundary'
import Icon from './components/Icon'
import Logo from './components/Logo'
import { AuthContext, useAuth, useAuthState } from './hooks/useAuth'
import AuditLog from './pages/AuditLog'
import ClaimsWorkbench from './pages/ClaimsWorkbench'
import JabAudit from './pages/JabAudit'
import Login from './pages/Login'
import NewClaim from './pages/NewClaim'
import RuleManager from './pages/RuleManager'
import UserGuide from './pages/UserGuide'
import Users from './pages/Users'
import { hashPath } from './utils/route'

// Loaded on demand: the chart library is most of its weight
const Dashboard = lazy(() => import('./pages/Dashboard'))

// Hash-based routes, so a refresh keeps the current page without a router library.
// Each needs a permission; pages the user's role lacks are left out of the menu.
// `admin` routes sit apart at the bottom of the sidebar.
const ROUTES = [
  { hash: '#/dashboard', label: 'Overview', icon: 'overview', Page: Dashboard, permission: 'claims:read' },
  { hash: '#/claims', label: 'Claims', icon: 'claims', Page: ClaimsWorkbench, permission: 'claims:read' },
  { hash: '#/new-claim', label: 'New Claim', icon: 'plus', Page: NewClaim, permission: 'claims:write' },
  { hash: '#/rules', label: 'Rules', icon: 'rules', Page: RuleManager, permission: 'rules:write' },
  { hash: '#/jab', label: 'JAB Audit', icon: 'loop', Page: JabAudit, permission: 'claims:read' },
  { hash: '#/guide', label: 'User Guide', icon: 'book', Page: UserGuide, permission: 'claims:read' },
  { hash: '#/users', label: 'Users', icon: 'users', Page: Users, permission: 'users:manage', admin: true },
  { hash: '#/audit', label: 'Audit Log', icon: 'shield', Page: AuditLog, permission: 'audit:read', admin: true },
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
    return <div className="flex min-h-screen items-center justify-center text-sm text-gray-400">Loading…</div>
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

function initials(name) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('')
}

function NavLink({ route, current }) {
  const active = route.hash === current
  return (
    <a
      href={route.hash}
      aria-current={active ? 'page' : undefined}
      className={`flex shrink-0 items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-colors ${
        active ? 'bg-white text-gray-900 shadow-sm ring-1 ring-gray-200/70' : 'text-gray-600 hover:bg-gray-200/50 hover:text-gray-900'
      }`}
    >
      <Icon name={route.icon} className={`h-[18px] w-[18px] ${active ? 'text-accent' : 'text-gray-400'}`} />
      {route.label}
    </a>
  )
}

function UserMenu({ user, onSignOut }) {
  return (
    <div className="flex items-center gap-3">
      <div
        aria-hidden="true"
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gray-200 text-xs font-semibold text-gray-700"
      >
        {initials(user.display_name)}
      </div>
      <div className="hidden min-w-0 flex-1 leading-tight sm:block">
        <div className="truncate text-sm font-medium text-gray-900">{user.display_name}</div>
        <div className="truncate text-xs text-gray-500" title={user.access ? `Sees only: ${user.access}` : undefined}>
          {ROLE_LABELS[user.role] ?? user.role}
          {user.access && ' · limited'}
        </div>
      </div>
      <button
        onClick={onSignOut}
        title="Sign out"
        className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-200/60 hover:text-gray-900"
      >
        <Icon name="signout" className="h-[18px] w-[18px]" />
        <span className="sr-only">Sign out</span>
      </button>
    </div>
  )
}

function Shell() {
  const auth = useAuth()
  const routes = ROUTES.filter((r) => auth.user.permissions.includes(r.permission))
  const { route, hash } = useHashRoute(routes)
  const { Page } = route
  const main = routes.filter((r) => !r.admin)
  const admin = routes.filter((r) => r.admin)

  return (
    <div className="min-h-screen lg:flex">
      {/* Phones: brand and account on one row, the menu scrolling below.
          Desktop: a sidebar with the account at the bottom. */}
      <aside className="sticky top-0 z-20 flex flex-wrap items-center gap-3 border-b border-gray-200/70 bg-canvas/90 px-4 py-3 backdrop-blur lg:h-screen lg:w-60 lg:shrink-0 lg:flex-col lg:flex-nowrap lg:items-stretch lg:gap-8 lg:border-r lg:border-b-0 lg:py-6">
        <div className="flex items-center gap-2.5 lg:px-2">
          <Logo />
          <div className="leading-tight">
            <div className="text-[15px] font-semibold tracking-tight text-gray-900">ClaustraRCM</div>
            {/* Whose data this is: each organisation's is kept apart from the others' */}
            <div className="truncate text-xs text-gray-500" title={auth.user.organisation?.name}>
              {auth.user.organisation?.name ?? 'Claim Validation'}
            </div>
          </div>
        </div>
        <div className="ml-auto lg:order-last lg:mt-auto lg:ml-0 lg:border-t lg:border-gray-200/70 lg:px-2 lg:pt-4">
          <UserMenu user={auth.user} onSignOut={auth.signOut} />
        </div>
        <nav
          aria-label="Main"
          className="-mx-4 flex w-[calc(100%+2rem)] gap-1 overflow-x-auto px-4 lg:mx-0 lg:w-auto lg:flex-col lg:overflow-visible lg:px-0"
        >
          {main.map((r) => (
            <NavLink key={r.hash} route={r} current={route.hash} />
          ))}
          {admin.length > 0 && (
            <>
              <div className="eyebrow hidden px-3 pt-6 pb-1 lg:block">Admin</div>
              {admin.map((r) => (
                <NavLink key={r.hash} route={r} current={route.hash} />
              ))}
            </>
          )}
        </nav>
      </aside>
      <main className="min-w-0 flex-1">
        {/* Keyed by the full hash so a new query (e.g. ?search=) starts the page fresh,
            and leaving a crashed page clears the error */}
        <ErrorBoundary key={hash}>
          <Suspense fallback={<div className="p-10 text-sm text-gray-400">Loading…</div>}>
            <Page />
          </Suspense>
        </ErrorBoundary>
      </main>
    </div>
  )
}

export default App
