import { useEffect, useId, useState } from 'react'
import Icon from '../components/Icon'
import Logo from '../components/Logo'
import { pilotContactEmail } from './content'
import { APP_PATH } from './router'
import { Link } from './Link'

// Fixed when the page loads; the site isn't left open across a new year
const YEAR = new Date().getFullYear()

const NAV = [
  { href: '/', label: 'Home' },
  { href: '/about', label: 'About' },
]

function Brand({ inverse = false }) {
  return (
    <Link href="/" className="flex items-center gap-2.5 rounded-lg" aria-label="VeriClaim home">
      <Logo />
      <span className={`text-[17px] font-semibold tracking-tight ${inverse ? 'text-white' : 'text-gray-900'}`}>
        VeriClaim
      </span>
    </Link>
  )
}

function SiteHeader({ path }) {
  const [scrolled, setScrolled] = useState(false)
  const [open, setOpen] = useState(false)
  const menuId = useId()

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    if (!open) return undefined
    const onKey = (event) => event.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const linkClass = (href) =>
    `rounded-full px-3 py-2 text-sm font-medium transition-colors ${
      path === href ? 'text-gray-900' : 'text-gray-600 hover:text-gray-900'
    }`

  return (
    <header
      className={`sticky top-0 z-40 transition-[background-color,box-shadow] duration-300 motion-reduce:transition-none ${
        scrolled || open ? 'bg-white/85 shadow-[0_1px_0_rgba(15,23,42,0.08)] backdrop-blur-xl' : 'bg-transparent'
      }`}
    >
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-5 sm:px-8">
        <Brand />
        <nav aria-label="Site" className="hidden items-center gap-1 md:flex">
          {NAV.map((item) => (
            <Link key={item.href} href={item.href} className={linkClass(item.href)} aria-current={path === item.href ? 'page' : undefined}>
              {item.label}
            </Link>
          ))}
          <span className="flex items-center text-sm text-gray-300" aria-hidden="true">
            ·
          </span>
          <a href={APP_PATH} className={linkClass(APP_PATH)}>
            Sign in
          </a>
          <Link href="/sign-up" className={linkClass('/sign-up')} aria-current={path === '/sign-up' ? 'page' : undefined}>
            Sign up
          </Link>
          <Link href="/pilot" className="btn-primary ml-2 px-4 py-2">
            Request a Pilot
          </Link>
        </nav>
        <button
          type="button"
          className="rounded-full p-2 text-gray-700 hover:bg-gray-100 md:hidden"
          aria-expanded={open}
          aria-controls={menuId}
          onClick={() => setOpen((value) => !value)}
        >
          <Icon name={open ? 'close' : 'claims'} className="h-5 w-5" />
          <span className="sr-only">{open ? 'Close menu' : 'Open menu'}</span>
        </button>
      </div>
      <nav id={menuId} aria-label="Site" hidden={!open} onClick={(event) => event.target.closest('a') && setOpen(false)} className="border-t border-gray-200/70 bg-white px-5 pt-2 pb-5 md:hidden">
        <ul className="space-y-1">
          {NAV.map((item) => (
            <li key={item.href}>
              <Link
                href={item.href}
                className="block rounded-xl px-3 py-3 text-base font-medium text-gray-900 hover:bg-gray-50"
                aria-current={path === item.href ? 'page' : undefined}
              >
                {item.label}
              </Link>
            </li>
          ))}
          <li>
            <a href={APP_PATH} className="block rounded-xl px-3 py-3 text-base font-medium text-gray-900 hover:bg-gray-50">
              Sign in
            </a>
          </li>
          <li>
            <Link href="/sign-up" className="block rounded-xl px-3 py-3 text-base font-medium text-gray-900 hover:bg-gray-50">
              Sign up
            </Link>
          </li>
        </ul>
        <Link href="/pilot" className="btn-primary mt-3 w-full py-3 text-base">
          Request a Pilot
        </Link>
      </nav>
    </header>
  )
}

function SiteFooter() {
  const contact = pilotContactEmail()
  const linkClass = 'text-sm text-gray-400 hover:text-white'
  return (
    <footer className="bg-navy text-white">
      <div className="mx-auto grid max-w-6xl gap-10 px-5 py-14 sm:px-8 md:grid-cols-[1.4fr_1fr_1fr]">
        <div className="max-w-sm space-y-4">
          <Brand inverse />
          <p className="text-sm leading-relaxed text-gray-400">
            Pre-submission claims validation for hospital billing teams. Find claim errors, correct them, and move clean claims
            forward.
          </p>
        </div>
        <nav aria-label="Footer">
          <div className="text-xs font-semibold tracking-wide text-gray-500 uppercase">Explore</div>
          <ul className="mt-4 space-y-2.5">
            <li><Link href="/" className={linkClass}>Home</Link></li>
            <li><Link href="/about" className={linkClass}>About</Link></li>
            <li><a href={APP_PATH} className={linkClass}>Sign in</a></li>
            <li><Link href="/pilot" className={linkClass}>Pilot interest</Link></li>
          </ul>
        </nav>
        <div>
          <div className="text-xs font-semibold tracking-wide text-gray-500 uppercase">Company</div>
          <ul className="mt-4 space-y-2.5">
            {contact && (
              <li>
                <a href={`mailto:${contact}`} className={linkClass}>
                  {contact}
                </a>
              </li>
            )}
            <li><Link href="/privacy" className={linkClass}>Privacy Policy</Link></li>
            <li><Link href="/terms" className={linkClass}>Terms of Use</Link></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-white/10">
        <p className="mx-auto max-w-6xl px-5 py-6 text-xs text-gray-500 sm:px-8">© {YEAR} VeriClaim. Demonstrations use synthetic data only.</p>
      </div>
    </footer>
  )
}

export default function SiteLayout({ path, children }) {
  return (
    <div className="flex min-h-screen flex-col bg-[#f8fafc]">
      <a
        href="#main"
        className="sr-only z-50 rounded-full bg-white px-4 py-2 text-sm font-medium shadow focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>
      <SiteHeader path={path} />
      <main id="main" tabIndex={-1} className="flex-1 focus:outline-none">
        {children}
      </main>
      <SiteFooter />
    </div>
  )
}
