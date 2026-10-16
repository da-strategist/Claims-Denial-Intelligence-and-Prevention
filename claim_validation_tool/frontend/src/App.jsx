import { lazy, Suspense, useEffect, useState } from 'react'
import ClaimsWorkbench from './pages/ClaimsWorkbench'
import RuleManager from './pages/RuleManager'

// Loaded on demand: the chart library is most of its weight
const Dashboard = lazy(() => import('./pages/Dashboard'))

// Hash-based routes, so a refresh keeps the current page without a router library
const ROUTES = [
  { hash: '#/dashboard', label: 'Dashboard', Page: Dashboard },
  { hash: '#/claims', label: 'Claims Workbench', Page: ClaimsWorkbench },
  { hash: '#/rules', label: 'Rule Manager', Page: RuleManager },
]

function useHashRoute() {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const onChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return ROUTES.find((route) => route.hash === hash) ?? ROUTES[0]
}

function App() {
  const route = useHashRoute()
  const { Page } = route

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="flex flex-wrap items-center gap-x-8 gap-y-3 border-b border-gray-200 bg-white px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-600 text-lg font-bold text-white">
            C
          </div>
          <div>
            <div className="font-semibold text-gray-900">ClaustraRCM</div>
            <div className="text-xs text-gray-500">Claim Validation</div>
          </div>
        </div>
        <nav aria-label="Main" className="flex gap-1">
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
        <Suspense fallback={<div className="p-6 text-sm text-gray-500">Loading…</div>}>
          <Page />
        </Suspense>
      </main>
    </div>
  )
}

export default App
