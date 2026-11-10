import { LEGAL } from '../content'
import { APP_PATH } from '../router'
import { Link } from '../Link'

function Page({ eyebrow, title, children, labelledBy }) {
  return (
    <section aria-labelledby={labelledBy} className="mx-auto max-w-2xl px-5 py-20 text-center sm:px-8 sm:py-28">
      {eyebrow && <div className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">{eyebrow}</div>}
      <h1 id={labelledBy} className="mt-4 text-4xl font-semibold tracking-tight text-balance text-gray-900 sm:text-5xl">
        {title}
      </h1>
      <div className="mt-6 space-y-6 text-lg leading-relaxed text-gray-600">{children}</div>
    </section>
  )
}

/** Sign up: the claims app has no self-registration. Accounts come from each organisation's
 * administrator, so this page explains that and leads to the pilot request. */
export function SignUp() {
  return (
    <Page eyebrow="Sign up" title="Access is by invitation during the pilot." labelledBy="signup-title">
      <p>
        VeriClaim accounts are created by your organization’s administrator, so every user belongs to a hospital and sees only
        that hospital’s claims.
      </p>
      <div className="flex flex-col items-center justify-center gap-3 sm:flex-row">
        <Link href="/pilot" className="btn-primary px-6 py-3 text-base">
          Request a Pilot
        </Link>
        <a href={APP_PATH} className="btn-secondary px-6 py-3 text-base">
          I have an account: Sign in
        </a>
      </div>
      <p className="text-sm text-gray-500">Already part of a pilot? Ask your administrator to add you.</p>
    </Page>
  )
}

/** Privacy Policy or Terms of Use: shown only once the owner has published them. */
export function Legal({ kind }) {
  const title = kind === 'privacy' ? 'Privacy Policy' : 'Terms of Use'
  const text = LEGAL[kind]
  return (
    <Page eyebrow="Legal" title={title} labelledBy="legal-title">
      {text ? (
        <div className="text-left text-base whitespace-pre-line">{text}</div>
      ) : (
        <p>Our {title} is being prepared and will be published here.</p>
      )}
    </Page>
  )
}

export function NotFound() {
  return (
    <Page eyebrow="Not found" title="This page doesn’t exist." labelledBy="notfound-title">
      <Link href="/" className="btn-primary px-6 py-3 text-base">
        Go to the home page
      </Link>
    </Page>
  )
}
