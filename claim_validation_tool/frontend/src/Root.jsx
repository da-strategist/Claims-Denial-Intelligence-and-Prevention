import { lazy, Suspense } from 'react'
import { APP_PATH } from './site/router'

// Each half loads only when it's needed: website visitors don't download the claims app,
// and the app doesn't carry the website
const App = lazy(() => import('./App'))
const Site = lazy(() => import('./site/Site'))

/**
 * Two pages in one build: the claims app at /app (its own hash routes, sign-in, and every
 * API call), and the public website everywhere else. Bookmarks from before the website
 * (/#/claims) still open the app.
 */
export default function Root() {
  const { pathname, hash } = window.location
  if (pathname === '/' && hash.startsWith('#/')) {
    window.location.replace(`${APP_PATH}${hash}`)
    return null
  }
  const app = pathname === APP_PATH || pathname.startsWith(`${APP_PATH}/`)
  return <Suspense fallback={null}>{app ? <App /> : <Site />}</Suspense>
}
