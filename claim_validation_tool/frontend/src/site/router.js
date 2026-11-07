import { useEffect, useState } from 'react'

// The public website's own small router: paths (/, /about, /pilot), no library. The claims
// app keeps its hash routes under /app.

export const APP_PATH = '/app'

const NAVIGATE_EVENT = 'site:navigate'

/** The current pathname, updated on back/forward and on navigate(). */
export function usePath() {
  const [path, setPath] = useState(window.location.pathname)
  useEffect(() => {
    const update = () => setPath(window.location.pathname)
    window.addEventListener('popstate', update)
    window.addEventListener(NAVIGATE_EVENT, update)
    return () => {
      window.removeEventListener('popstate', update)
      window.removeEventListener(NAVIGATE_EVENT, update)
    }
  }, [])
  return path
}

/** Go to a site path ("/about", "/#demo"): same page anchors scroll, new pages start at the top. */
export function navigate(href) {
  const url = new URL(href, window.location.origin)
  if (url.pathname.startsWith(APP_PATH)) {
    window.location.assign(url.pathname + url.hash) // the app is a separate page
    return
  }
  const samePage = url.pathname === window.location.pathname
  if (!samePage) {
    window.history.pushState({}, '', url.pathname + url.hash)
    window.dispatchEvent(new Event(NAVIGATE_EVENT))
  }
  // After the new page renders
  requestAnimationFrame(() => {
    const target = url.hash && document.getElementById(url.hash.slice(1))
    if (target) {
      if (samePage) window.history.replaceState({}, '', url.pathname + url.hash)
      target.scrollIntoView?.({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'start' })
      target.focus?.({ preventScroll: true })
    } else {
      window.scrollTo(0, 0)
    }
  })
}

export function prefersReducedMotion() {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}
