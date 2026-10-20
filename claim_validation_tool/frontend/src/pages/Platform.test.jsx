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

  it('flags a missing BAA and records one', async () => {
    const user = userEvent.setup()
    const fetchMock = setup({
      'POST /platform/organisations/acme/baa': ({ body }) => ({ ...ORGS[1], baa: body }),
    })
    const acme = await row('Acme Health')
    expect(within(acme).getByText('No business associate agreement on record')).toBeInTheDocument()
    await user.click(within(acme).getByRole('button', { name: 'Record BAA for Acme Health' }))
    const form = within(acme).getByRole('form', { name: 'Business associate agreement for Acme Health' })
    await user.type(within(form).getByLabelText('Signed on'), '2026-10-01')
    await user.type(within(form).getByLabelText('Reference'), 'BAA-2026-014')
    await user.type(within(form).getByLabelText(/Signed by/), 'Dr. Ada Obi')
    await user.click(within(form).getByRole('button', { name: 'Record agreement' }))
    expect(await screen.findByText('Acme Health’s business associate agreement is on record.')).toBeInTheDocument()
    expect(sentBodies(fetchMock, 'POST /platform/organisations/acme/baa')).toEqual([
      { signed_on: '2026-10-01', reference: 'BAA-2026-014', signatory: 'Dr. Ada Obi' },
    ])
  })

  it('deletes a suspended organisation only once its ID is typed', async () => {
    const user = userEvent.setup()
    const suspended = { ...ORGS[1], status: 'suspended' }
    const fetchMock = setup({
      'GET /platform/organisations': () => [ORGS[0], suspended],
      'POST /platform/organisations/acme/delete': () => ({
        organisation: { ...suspended, status: 'deleted' },
        done: ['deleted its folder (acme/)'],
      }),
    })
    const lakeside = await row('Lakeside Family Practice')
    expect(within(lakeside).queryByRole('button', { name: /Delete/ })).not.toBeInTheDocument() // active
    const acme = await row('Acme Health')
    await user.click(within(acme).getByRole('button', { name: 'Delete Acme Health' }))
    const form = within(acme).getByRole('form', { name: 'Delete Acme Health' })
    const go = within(form).getByRole('button', { name: 'Delete for good' })
    await user.type(within(form).getByLabelText('Type acme to confirm'), 'Acme')
    expect(go).toBeDisabled()
    await user.clear(within(form).getByLabelText('Type acme to confirm'))
    await user.type(within(form).getByLabelText('Type acme to confirm'), 'acme')
    await user.click(go)
    expect(await screen.findByText(/Acme Health was deleted: deleted its folder/)).toBeInTheDocument()
    expect(sentBodies(fetchMock, 'POST /platform/organisations/acme/delete')).toEqual([{ confirm: 'acme' }])
  })

  it('shows deleted organisations as a record only', async () => {
    setup({
      'GET /platform/organisations': () => [{ ...ORGS[1], status: 'deleted', deleted_at: '2026-10-17T12:00:00Z' }],
    })
    const acme = await row('Acme Health')
    expect(within(acme).getByText(/deleted/)).toBeInTheDocument()
    expect(within(acme).queryByRole('button')).not.toBeInTheDocument()
  })
})
