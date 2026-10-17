import { lazy, Suspense, useEffect, useState } from 'react'
import ErrorBoundary from './components/ErrorBoundary'
import ClaimsWorkbench from './pages/ClaimsWorkbench'
import JabAudit from './pages/JabAudit'
import NewClaim from './pages/NewClaim'
import RuleManager from './pages/RuleManager'
import { hashPath } from './utils/route'

// Loaded on demand: the chart library is most of its weight
const Dashboard = lazy(() => import('./pages/Dashboard'))

// Hash-based routes, so a refresh keeps the current page without a router library
const ROUTES = [
  { hash: '#/dashboard', label: 'Dashboard', Page: Dashboard },
  { hash: '#/claims', label: 'Claims Workbench', Page: ClaimsWorkbench },
  { hash: '#/new-claim', label: 'New Claim', Page: NewClaim },
  { hash: '#/rules', label: 'Rule Manager', Page: RuleManager },
  { hash: '#/jab', label: 'JAB Audit', Page: JabAudit },
]

function useHashRoute() {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const onChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  const route = ROUTES.find((r) => r.hash === hashPath(hash)) ?? ROUTES[0]
  return { route, hash }
}

function App() {
  const { route, hash } = useHashRoute()
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
          {ROUTES.map(({ hash, label }) => (
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
