import { useEffect } from 'react'
import About from './pages/About'
import Home from './pages/Home'
import Pilot from './pages/Pilot'
import { Legal, NotFound, SignUp } from './pages/SimplePages'
import SiteLayout from './SiteLayout'
import { APP_PATH, usePath } from './router'

const PAGES = {
  '/': { Page: Home, title: 'VeriClaim — Catch claim errors before submission' },
  '/about': { Page: About, title: 'About — VeriClaim' },
  '/pilot': { Page: Pilot, title: 'Request a pilot — VeriClaim' },
  '/sign-up': { Page: SignUp, title: 'Sign up — VeriClaim' },
  '/privacy': { Page: () => <Legal kind="privacy" />, title: 'Privacy Policy — VeriClaim' },
  '/terms': { Page: () => <Legal kind="terms" />, title: 'Terms of Use — VeriClaim' },
}

/** The public website: Home, About, pilot requests, sign-up information and legal pages.
 * Signing in happens in the app itself, at /app. */
export default function Site() {
  const path = usePath().replace(/\/+$/, '') || '/'
  const page = PAGES[path]

  useEffect(() => {
    document.title = page?.title ?? 'Page not found — VeriClaim'
  }, [page])

  // A new page (not the first) moves focus to its content, for screen readers and keyboards
  useEffect(() => {
    if (window.location.hash) return
    const main = document.getElementById('main')
    if (main && document.activeElement !== document.body) main.focus({ preventScroll: true })
  }, [path])

  if (path === '/sign-in' || path === '/login') {
    window.location.replace(APP_PATH)
    return null
  }

  const { Page } = page ?? { Page: NotFound }
  return (
    <SiteLayout path={path}>
      <Page />
    </SiteLayout>
  )
}
