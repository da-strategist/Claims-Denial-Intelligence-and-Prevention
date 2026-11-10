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
    'GET /platform/pilot-requests': () => [],
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

  it('creates an organisation together with its first administrator', async () => {
    const user = userEvent.setup()
    const fetchMock = setup({
      'POST /platform/organisations': ({ body }) =>
        reply(201, { id: body.id, name: body.name, status: 'active', accounts: 1, active_admins: 1 }),
    })
    await user.click(await screen.findByRole('button', { name: 'New organisation' }))
    const form = screen.getByRole('form', { name: 'New organisation' })
    const create = within(form).getByRole('button', { name: 'Create organisation' })
    await user.type(within(form).getByLabelText('Name'), 'Riverbend Clinic')
    await user.type(within(form).getByLabelText(/ID/), 'Riverbend')
    expect(create).toBeDisabled() // no administrator yet
    const admin = within(form).getByRole('group', { name: 'First administrator' })
    await user.type(within(admin).getByLabelText('Full name'), 'Rita Moss')
    await user.type(within(admin).getByLabelText('Username'), 'RMoss')
    await user.type(within(admin).getByLabelText('Password'), 'Riverbend-admin-1')
    await user.type(within(admin).getByLabelText(/Repeat|Confirm/), 'Riverbend-admin-1')
    await user.click(create)
    expect(await screen.findByText(/Riverbend Clinic is ready, and Rita Moss can sign in as rmoss/)).toBeInTheDocument()
    expect(sentBodies(fetchMock, 'POST /platform/organisations')).toEqual([
      {
        id: 'riverbend',
        name: 'Riverbend Clinic',
        admin: { display_name: 'Rita Moss', username: 'rmoss', password: 'Riverbend-admin-1' },
      },
    ])
  })

  it('keeps the form and says why when the organisation can’t be created', async () => {
    const user = userEvent.setup()
    setup({
      'POST /platform/organisations': () => reply(409, { detail: 'The username admin1 is taken; choose another' }),
    })
    await user.click(await screen.findByRole('button', { name: 'New organisation' }))
    const form = screen.getByRole('form', { name: 'New organisation' })
    await user.type(within(form).getByLabelText('Name'), 'Riverbend Clinic')
    await user.type(within(form).getByLabelText(/ID/), 'riverbend')
    await user.type(within(form).getByLabelText('Full name'), 'Rita Moss')
    await user.type(within(form).getByLabelText('Username'), 'admin1')
    await user.type(within(form).getByLabelText('Password'), 'Riverbend-admin-1')
    await user.type(within(form).getByLabelText(/Repeat|Confirm/), 'Riverbend-admin-1')
    await user.click(within(form).getByRole('button', { name: 'Create organisation' }))
    expect(await within(form).findByText(/admin1 is taken/)).toBeInTheDocument()
    expect(within(form).getByLabelText('Name')).toHaveValue('Riverbend Clinic')
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

const REQUEST = {
  id: 'PR-1a2b3c4d',
  name: 'Grace Adeyemi',
  email: 'Grace.Adeyemi@valleyhospital.org',
  organization: 'Valley Critical Access Hospital',
  title: 'Revenue cycle director',
  org_type: 'Critical Access Hospital',
  message: 'About 900 claims a month.',
  received_at: '2026-11-06T09:00:00Z',
  status: 'pending',
}

describe('Pilot requests', () => {
  it('approves a request with an organisation filled in from it', async () => {
    const user = userEvent.setup()
    const fetchMock = setup({
      'GET /platform/pilot-requests': () => [REQUEST],
      'POST /platform/pilot-requests/PR-1a2b3c4d/approve': ({ body }) => ({ ...ORGS[0], ...body.organisation }),
    })
    expect(await screen.findByRole('heading', { name: /Pilot requests · 1 pending/ })).toBeInTheDocument()
    const item = await row('Valley Critical Access Hospital')
    expect(within(item).getByText('About 900 claims a month.')).toBeInTheDocument()
    await user.click(within(item).getByRole('button', { name: 'Approve' }))

    const form = screen.getByRole('form', { name: 'New organisation' })
    expect(within(form).getByLabelText('Name')).toHaveValue('Valley Critical Access Hospital')
    expect(within(form).getByLabelText('ID (short, lower case)')).toHaveValue('valley-critical-access-hospital')
    expect(within(form).getByLabelText('Full name')).toHaveValue('Grace Adeyemi')
    expect(within(form).getByLabelText('Username')).toHaveValue('grace.adeyemi')
    await user.clear(within(form).getByLabelText('ID (short, lower case)'))
    await user.type(within(form).getByLabelText('ID (short, lower case)'), 'valley')
    await user.type(within(form).getByLabelText('Password'), 'Valley-temp-123')
    await user.type(within(form).getByLabelText('Repeat password'), 'Valley-temp-123')
    await user.click(within(form).getByRole('button', { name: 'Approve and create' }))

    expect(await screen.findByText(/is ready, and Grace Adeyemi can sign in as grace.adeyemi/)).toBeInTheDocument()
    expect(sentBodies(fetchMock, 'POST /platform/pilot-requests/PR-1a2b3c4d/approve')[0]).toEqual({
      organisation: {
        id: 'valley',
        name: 'Valley Critical Access Hospital',
        admin: { display_name: 'Grace Adeyemi', username: 'grace.adeyemi', password: 'Valley-temp-123' },
      },
    })
  })

  it('declines with a reason and keeps decided requests out of the way', async () => {
    const user = userEvent.setup()
    const fetchMock = setup({
      'GET /platform/pilot-requests': () => [
        REQUEST,
        { ...REQUEST, id: 'PR-old', organization: 'Old Clinic', status: 'declined', decided_by: 'platform1', decided_at: '2026-11-01T09:00:00Z', decline_reason: 'Not a fit' },
      ],
      'POST /platform/pilot-requests/PR-1a2b3c4d/decline': () => ({ ...REQUEST, status: 'declined' }),
    })
    const item = await row('Valley Critical Access Hospital')
    expect(screen.queryByText('Old Clinic')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Show decided requests (1)' }))
    expect(screen.getByText(/Declined by platform1: “Not a fit”/)).toBeInTheDocument()

    await user.click(within(item).getByRole('button', { name: 'Decline' }))
    const decline = within(item).getByRole('button', { name: 'Decline request' })
    expect(decline).toBeDisabled()
    await user.type(within(item).getByLabelText('Reason (kept for the record)'), 'Outside the US for now')
    await user.click(decline)
    expect(await screen.findByText(/request was declined/)).toBeInTheDocument()
    expect(sentBodies(fetchMock, 'POST /platform/pilot-requests/PR-1a2b3c4d/decline')[0]).toEqual({
      reason: 'Outside the US for now',
    })
  })
})
