import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { AuthContext } from '../hooks/useAuth'
import { mockApi, reply, sentBodies } from '../test/mockApi'
import Platform from './Platform'

const ORGS = [
  { id: 'lakeside', name: 'Lakeside Family Practice', status: 'active', created_at: '2026-10-17T10:00:00Z', accounts: 1, active_admins: 1 },
  { id: 'acme', name: 'Acme Health', status: 'active', created_at: '2026-10-17T10:00:00Z', accounts: 0, active_admins: 0 },
]

function setup(extra = {}) {
  const fetchMock = mockApi({
    'GET /platform/organisations': () => ORGS,
    'GET /platform/emergency-access': () => [],
    'GET /platform/audit': () => [],
    ...extra,
  })
  const refresh = async () => ({ emergency: { id: 'EA-1' } })
  render(
    <AuthContext.Provider value={{ user: { username: 'platform1', permissions: ['platform:manage'] }, refresh }}>
      <Platform />
    </AuthContext.Provider>,
  )
  return fetchMock
}

const row = async (name) => (await screen.findByText(name)).closest('li')

describe('Platform', () => {
  it('lists organisations and flags one without an administrator', async () => {
    setup()
    expect(within(await row('Acme Health')).getByText('no active administrator')).toBeInTheDocument()
    expect(within(await row('Lakeside Family Practice')).getByText(/1 active admin/)).toBeInTheDocument()
  })

  it('starts emergency access only with a real reason, then opens the organisation', async () => {
    const user = userEvent.setup()
    const fetchMock = setup({
      'POST /platform/organisations/lakeside/emergency-access': () => reply(201, { id: 'EA-1' }),
    })
    const lakeside = await row('Lakeside Family Practice')
    await user.click(within(lakeside).getByRole('button', { name: 'Emergency access' }))
    const form = within(lakeside).getByRole('form', { name: 'Emergency access to Lakeside Family Practice' })
    const start = within(form).getByRole('button', { name: 'Start read-only access' })
    await user.type(within(form).getByLabelText(/Reason/), 'just looking')
    expect(start).toBeDisabled()
    await user.type(within(form).getByLabelText(/Reason/), ' into ticket 4471 for their billing team')
    await user.selectOptions(within(form).getByLabelText('For'), '30')
    await user.click(start)
    await waitFor(() => expect(window.location.hash).toBe('#/dashboard'))
    expect(sentBodies(fetchMock, 'POST /platform/organisations/lakeside/emergency-access')).toEqual([
      { reason: 'just looking into ticket 4471 for their billing team', minutes: 30 },
    ])
  })

  it('creates an organisation', async () => {
    const user = userEvent.setup()
    const fetchMock = setup({
      'POST /platform/organisations': ({ body }) => reply(201, { ...body, status: 'active', accounts: 0, active_admins: 0 }),
    })
    await user.click(await screen.findByRole('button', { name: 'New organisation' }))
    const form = screen.getByRole('form', { name: 'New organisation' })
    await user.type(within(form).getByLabelText('Name'), 'Riverbend Clinic')
    await user.type(within(form).getByLabelText(/ID/), 'Riverbend')
    await user.click(within(form).getByRole('button', { name: 'Create organisation' }))
    expect(await screen.findByText(/Riverbend Clinic is ready/)).toBeInTheDocument()
    expect(sentBodies(fetchMock, 'POST /platform/organisations')).toEqual([{ id: 'riverbend', name: 'Riverbend Clinic' }])
  })
})
