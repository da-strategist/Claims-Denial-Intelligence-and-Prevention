import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import App from './App'
import { SIGNED_OUT_EVENT } from './services/api'
import { mockApi, reply, sentBodies } from './test/mockApi'

const user = (role, permissions) => ({
  username: `${role}1`,
  display_name: `Test ${role}`,
  role,
  permissions,
  idle_timeout_minutes: 15,
  organisation: { id: 'meridian', name: 'Meridian Regional Medical Center' },
  session_expires_at: '2026-10-17T20:00:00Z',
})
const ANALYST = user('analyst', ['claims:read'])
const ADMIN = user('admin', ['audit:read', 'claims:read', 'claims:write', 'patients:read', 'rules:write', 'users:manage'])

const PAGE = { 'GET /jab/contracts': () => [] }
const signedOut = { 'GET /auth/me': () => reply(401, { detail: 'Sign in to continue' }) }
const navLinks = () =>
  within(screen.getByRole('navigation', { name: 'Main' }))
    .getAllByRole('link')
    .map((link) => link.textContent)

const PLATFORM = { ...user('platform', ['platform:manage']), organisation: null }
const PLATFORM_PAGE = {
  'GET /platform/organisations': () => [
    { id: 'lakeside', name: 'Lakeside Family Practice', status: 'active', created_at: '2026-10-17T10:00:00Z', accounts: 1, active_admins: 1 },
  ],
  'GET /platform/emergency-access': () => [],
  'GET /platform/audit': () => [],
}

describe('platform accounts', () => {
  it('see only the Platform page, with no organisation', async () => {
    window.location.hash = '#/claims'
    mockApi({ ...PLATFORM_PAGE, 'GET /auth/me': () => PLATFORM })
    render(<App />)
    expect(await screen.findByText('Lakeside Family Practice')).toBeInTheDocument()
    expect(navLinks()).toEqual(['Platform'])
  })

  it('work read-only under a banner during emergency access', async () => {
    window.location.hash = '#/jab'
    const inside = {
      ...PLATFORM,
      permissions: ['claims:read', 'patients:read', 'platform:manage'],
      organisation: { id: 'lakeside', name: 'Lakeside Family Practice' },
      emergency: { id: 'EA-1', reason: 'Ticket 4471: claims page fails to load', expires_at: '2026-10-17T15:00:00Z' },
    }
    mockApi({ ...PAGE, ...PLATFORM_PAGE, 'GET /auth/me': () => inside })
    render(<App />)
    const banner = await screen.findByRole('alert')
    expect(banner).toHaveTextContent('Emergency access to Lakeside Family Practice')
    expect(banner).toHaveTextContent('Read-only')
    expect(banner).toHaveTextContent('Ticket 4471')
    expect(navLinks()).toEqual(['Overview', 'Claims', 'JAB Audit', 'User Guide', 'Platform'])
  })
})

describe('organisation', () => {
  it('shows whose data the signed-in user is working in', async () => {
    mockApi({ ...PAGE, 'GET /auth/me': () => ANALYST })
    window.location.hash = '#/jab'
    render(<App />)
    expect(await screen.findByText('Meridian Regional Medical Center')).toBeInTheDocument()
  })
})

describe('signing in', () => {
  beforeEach(() => {
    window.location.hash = '#/jab'
  })

  it('shows the sign-in form until the password is right', async () => {
    const fetchMock = mockApi({
      ...signedOut,
      ...PAGE,
      'POST /auth/login': ({ body }) =>
        body.password === 'Right-password-1'
          ? ANALYST
          : reply(401, { detail: 'Wrong username or password' }),
    })
    render(<App />)
    const form = await screen.findByRole('form', { name: 'Sign in' })
    await userEvent.type(within(form).getByLabelText('Username'), 'analyst1')
    await userEvent.type(within(form).getByLabelText('Password'), 'nope')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Wrong username or password')
    expect(screen.getByLabelText('Password')).toHaveValue('')

    await userEvent.type(screen.getByLabelText('Password'), 'Right-password-1')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Test analyst')).toBeInTheDocument()
    expect(sentBodies(fetchMock, 'POST /auth/login').at(-1)).toEqual({
      username: 'analyst1',
      password: 'Right-password-1',
    })
  })

  it('shows analysts only the read-only pages', async () => {
    mockApi({ ...PAGE, 'GET /auth/me': () => ANALYST })
    render(<App />)
    await screen.findByText('Test analyst')
    expect(navLinks()).toEqual(['Overview', 'Claims', 'JAB Audit', 'User Guide'])
  })

  it('shows admins every page, including the audit log', async () => {
    mockApi({ ...PAGE, 'GET /auth/me': () => ADMIN })
    render(<App />)
    await screen.findByText('Administrator')
    expect(navLinks()).toEqual([
      'Overview',
      'Claims',
      'New Claim',
      'Rules',
      'JAB Audit',
      'User Guide',
      'Users',
      'Audit Log',
    ])
  })

  it('returns to sign-in when the session ends on the server', async () => {
    mockApi({ ...PAGE, 'GET /auth/me': () => ANALYST })
    render(<App />)
    await screen.findByText('Test analyst')
    act(() => window.dispatchEvent(new Event(SIGNED_OUT_EVENT)))
    expect(await screen.findByRole('status')).toHaveTextContent('Your session ended')
  })

  it('signs out', async () => {
    const fetchMock = mockApi({
      ...PAGE,
      'GET /auth/me': () => ANALYST,
      'POST /auth/logout': () => reply(204),
    })
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: 'Sign out' }))
    expect(await screen.findByRole('status')).toHaveTextContent('You signed out.')
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/auth/logout'))).toBe(true)
  })
})

describe('Audit Log page', () => {
  it('lists events and reports an intact hash chain', async () => {
    window.location.hash = '#/audit'
    const fetchMock = mockApi({
      'GET /auth/me': () => ADMIN,
      'GET /audit/verify': () => ({ ok: true, events: 1234, first_bad_seq: null }),
      'GET /audit': () => [
        {
          seq: 2,
          at: '2026-10-17T14:00:00Z',
          username: 'analyst1',
          role: 'analyst',
          action: 'GET /api/patients',
          records: {},
          query: {},
          detail: {},
          status_code: 403,
          outcome: 'denied',
          client_ip: '127.0.0.1',
          prev_hash: 'a',
          hash: 'b',
        },
      ],
    })
    render(<App />)
    expect(await screen.findByText(/Hash chain intact across 1,234 events/)).toBeInTheDocument()
    expect(screen.getByText('GET /api/patients')).toBeInTheDocument()
    expect(screen.getByText('403 denied')).toBeInTheDocument()

    await userEvent.type(screen.getByLabelText('Record ID'), 'CLM0000002')
    await userEvent.click(screen.getByRole('button', { name: 'Filter' }))
    const params = fetchMock.mock.calls
      .map(([url]) => new URL(url, 'http://localhost'))
      .filter((url) => url.pathname === '/api/audit')
      .map((url) => url.searchParams.get('record_id'))
    expect(params).toEqual([null, 'CLM0000002'])
  })

  it('flags a tampered log', async () => {
    window.location.hash = '#/audit'
    mockApi({
      'GET /auth/me': () => ADMIN,
      'GET /audit/verify': () => ({ ok: false, events: 10, first_bad_seq: 7 }),
      'GET /audit': () => [],
    })
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('altered at event 7')
  })
})
