import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Root from '../Root'
import ClaimDemo from './ClaimDemo'
import { pilotEmail } from './pilotEmail'
import Site from './Site'
import { mockApi, reply } from '../test/mockApi'

function at(url) {
  window.history.replaceState({}, '', url)
}

function reducedMotion(on = true) {
  vi.stubGlobal('matchMedia', (query) => ({ matches: on && query.includes('reduce'), media: query, addEventListener() {}, removeEventListener() {} }))
}

beforeEach(() => {
  at('/')
  vi.unstubAllEnvs()
})

describe('routing between the website and the app', () => {
  it('shows the website at / and the app at /app', async () => {
    mockApi({ 'GET /auth/me': () => reply(401, { detail: 'Sign in to continue' }) })
    render(<Root />)
    expect(await screen.findByRole('heading', { level: 1, name: /Catch Claim Errors/ })).toBeInTheDocument()
  })

  it('opens the app, and its sign-in, at /app', async () => {
    at('/app')
    mockApi({ 'GET /auth/me': () => reply(401, { detail: 'Sign in to continue' }) })
    render(<Root />)
    expect(await screen.findByRole('form', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('sends bookmarks from before the website to the app', () => {
    const replace = vi.fn()
    vi.stubGlobal('location', { ...window.location, pathname: '/', hash: '#/claims', replace })
    render(<Root />)
    expect(replace).toHaveBeenCalledWith('/app#/claims')
  })
})

describe('site navigation', () => {
  it('moves between pages without reloading, and sign-in goes to the app', async () => {
    render(<Site />)
    const nav = screen.getAllByRole('navigation', { name: 'Site' })[0]
    expect(within(nav).getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/app')
    await userEvent.click(within(nav).getByRole('link', { name: 'About' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Better Claims Start Before Submission.' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/about')
    expect(document.title).toBe('About — ClaustraRCM')
  })

  it('opens and closes the mobile menu', async () => {
    render(<Site />)
    const toggle = screen.getByRole('button', { name: 'Open menu' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(toggle)
    expect(screen.getByRole('button', { name: 'Close menu' })).toHaveAttribute('aria-expanded', 'true')
    await userEvent.keyboard('{Escape}')
    expect(screen.getByRole('button', { name: 'Open menu' })).toHaveAttribute('aria-expanded', 'false')
  })

  it('shows a not-found page for unknown paths', () => {
    at('/nowhere')
    render(<Site />)
    expect(screen.getByRole('heading', { name: 'This page doesn’t exist.' })).toBeInTheDocument()
  })

  it('says sign-up is by invitation and leads to the pilot request', () => {
    at('/sign-up')
    render(<Site />)
    expect(screen.getByRole('heading', { level: 1, name: /by invitation/ })).toBeInTheDocument()
    expect(within(screen.getByRole('main')).getByRole('link', { name: 'Request a Pilot' })).toHaveAttribute('href', '/pilot')
  })

  it('labels unapproved and missing About content instead of inventing it', () => {
    at('/about')
    render(<Site />)
    expect(screen.getAllByText('Draft · pending approval')).toHaveLength(2)
    expect(screen.getByText(/Team profiles will appear here/)).toBeInTheDocument()
  })

  it('switches showcase tabs with the arrow keys', async () => {
    render(<Site />)
    const tabs = screen.getByRole('tablist', { name: 'Product views' })
    const first = within(tabs).getByRole('tab', { name: 'Claims queue' })
    first.focus()
    await userEvent.keyboard('{ArrowRight}')
    expect(within(tabs).getByRole('tab', { name: 'Errors & corrections' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tabpanel')).toHaveTextContent('Every error explained')
  })
})

describe('the interactive demo', () => {
  it('takes a claim from load through correction to send', async () => {
    reducedMotion()
    render(<ClaimDemo />)
    expect(screen.getByText('Not validated')).toBeInTheDocument()
    expect(screen.getByText('Demonstration · synthetic data')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Validate claim' }))
    expect(screen.getByText('Unclean · Review required')).toBeInTheDocument()
    expect(screen.getByText(/Error · Diagnosis Not Covered/)).toBeInTheDocument()
    expect(screen.getByText(/LCD-L33631/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Apply K21.0' }))
    expect(screen.getByText('Corrected · Revalidate')).toBeInTheDocument()
    expect(screen.getAllByText('K21.0').length).toBeGreaterThan(0)

    await userEvent.click(screen.getByRole('button', { name: 'Revalidate' }))
    expect(screen.getByText('Clean · Passed validation')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Continue to Send/ }))
    expect(screen.getByText('Hand off to your billing system')).toBeInTheDocument()
    // Submission is described as it is: no direct payer submission today
    expect(screen.getByText('Planned')).toBeInTheDocument()
    expect(screen.getByText(/doesn’t transmit claims to payers today/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Export corrected 837' }))
    expect(screen.getByText(/nothing is sent/)).toBeInTheDocument()
  })

  it('passes a clean claim straight through', async () => {
    reducedMotion()
    render(<ClaimDemo />)
    await userEvent.click(screen.getByRole('button', { name: /Office visit/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Validate claim' }))
    expect(screen.getByText('Clean · Passed validation')).toBeInTheDocument()
  })

  it('walks through the checks one by one when motion is welcome', async () => {
    reducedMotion(false)
    vi.useFakeTimers({ shouldAdvanceTime: true })
    render(<ClaimDemo />)
    await userEvent.click(screen.getByRole('button', { name: /Brain MRI/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Validate claim' }))
    expect(screen.getByText('Validating…')).toBeInTheDocument()
    await vi.advanceTimersByTimeAsync(2000)
    expect(screen.getByText(/Error · Missing Prior Authorization/)).toBeInTheDocument()
    vi.useRealTimers()
  })
})

describe('the pilot form', () => {
  it('says requests are not open until a contact address is configured', () => {
    at('/pilot')
    render(<Site />)
    expect(screen.getByText(/aren’t open on this site yet/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continue in your email app' })).toBeDisabled()
  })

  it('checks the details, then opens an email addressed to the pilot contact', async () => {
    vi.stubEnv('VITE_PILOT_CONTACT_EMAIL', 'pilots@example.org')
    at('/pilot')
    render(<Site />)
    await userEvent.click(screen.getByRole('button', { name: 'Continue in your email app' }))
    expect(screen.getByText('Enter your full name.')).toBeInTheDocument()
    expect(screen.getByLabelText('Full name')).toHaveFocus()

    const hrefs = []
    vi.stubGlobal('location', {
      ...window.location,
      set href(value) {
        hrefs.push(value)
      },
    })
    await userEvent.type(screen.getByLabelText('Full name'), 'Alex Rivera')
    await userEvent.type(screen.getByLabelText('Work email'), 'alex@hospital.org')
    await userEvent.type(screen.getByLabelText('Hospital or organization'), 'Valley Critical Access Hospital')
    await userEvent.type(screen.getByLabelText('Job title'), 'Revenue Cycle Director')
    await userEvent.selectOptions(screen.getByLabelText('Organization type'), 'Critical Access Hospital')
    await userEvent.click(screen.getByRole('button', { name: 'Continue in your email app' }))
    expect(hrefs[0]).toMatch(/^mailto:pilots@example\.org\?subject=Pilot%20interest%3A%20Valley/)
    expect(screen.getByRole('heading', { name: 'Your email app should now be open' })).toBeInTheDocument()
  })

  it('writes every field into the email', () => {
    vi.stubEnv('VITE_PILOT_CONTACT_EMAIL', 'pilots@example.org')
    const url = pilotEmail({
      name: 'A',
      email: 'a@b.org',
      organization: 'Org & Co',
      title: 'CFO',
      orgType: 'Rural hospital',
      message: 'Hello',
    })
    const body = decodeURIComponent(url.split('&body=')[1])
    expect(body).toContain('Organization: Org & Co')
    expect(body).toContain('Organization type: Rural hospital')
    expect(body.endsWith('Hello')).toBe(true)
  })
})
