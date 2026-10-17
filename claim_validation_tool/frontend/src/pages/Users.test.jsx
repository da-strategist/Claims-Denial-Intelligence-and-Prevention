import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { AuthContext } from '../hooks/useAuth'
import { mockApi, reply, sentBodies } from '../test/mockApi'
import Users from './Users'

const account = (username, display_name, role, active = true) => ({
  username,
  display_name,
  role,
  active,
  created_at: '2026-10-01T10:00:00Z',
  password_changed_at: '2026-10-01T10:00:00Z',
})

let accounts
let user

beforeEach(() => {
  user = userEvent.setup()
  accounts = [account('jubril', 'Jubril Olalekan', 'admin'), account('amina', 'Amina Bello', 'biller')]
})

function setup(extra = {}) {
  const fetchMock = mockApi({
    'GET /users': () => accounts,
    'POST /users': ({ body }) => {
      const created = account(body.username, body.display_name, body.role)
      accounts = [...accounts, created]
      return reply(201, created)
    },
    'PATCH /users/amina': ({ body }) => {
      accounts = accounts.map((a) => (a.username === 'amina' ? { ...a, ...body } : a))
      return accounts.find((a) => a.username === 'amina')
    },
    'POST /users/amina/password': () => reply(204),
    ...extra,
  })
  render(
    <AuthContext.Provider value={{ user: { username: 'jubril', permissions: ['users:manage'] } }}>
      <Users />
    </AuthContext.Provider>,
  )
  return fetchMock
}

const row = async (name) => (await screen.findByText(name)).closest('li')

describe('Users', () => {
  it('adds a user once the password meets the policy', async () => {
    const fetchMock = setup()
    await user.click(await screen.findByRole('button', { name: 'Add user' }))
    const form = screen.getByRole('form', { name: 'Add user' })
    await user.type(within(form).getByLabelText('Full name'), 'Kofi Mensah')
    await user.type(within(form).getByLabelText('Username'), 'Kofi')
    await user.selectOptions(within(form).getByLabelText('Role'), 'analyst')
    await user.type(within(form).getByLabelText('Password'), 'weakpassword')
    const submit = within(form).getByRole('button', { name: 'Add user' })
    expect(submit).toBeDisabled()

    await user.clear(within(form).getByLabelText('Password'))
    await user.type(within(form).getByLabelText('Password'), 'Strong-pass-123')
    await user.type(within(form).getByLabelText('Repeat password'), 'Strong-pass-123')
    expect(submit).toBeEnabled()
    await user.click(submit)

    expect(await screen.findByText(/Kofi Mensah can now sign in as kofi \(analyst\)/)).toBeInTheDocument()
    expect(sentBodies(fetchMock, 'POST /users')).toEqual([
      { display_name: 'Kofi Mensah', username: 'kofi', role: 'analyst', password: 'Strong-pass-123' },
    ])
  })

  it('changes roles and disables accounts, with a confirmation', async () => {
    const fetchMock = setup()
    const amina = await row('Amina Bello')
    await user.selectOptions(within(amina).getByLabelText('Role for amina'), 'admin')
    expect(await screen.findByText('Amina Bello is now administrator.')).toBeInTheDocument()

    await user.click(within(amina).getByRole('button', { name: 'Disable amina' }))
    await user.click(within(amina).getByRole('button', { name: 'Disable' }))
    expect(await screen.findByText('Amina Bello is disabled and signed out.')).toBeInTheDocument()
    expect(sentBodies(fetchMock, 'PATCH /users/amina')).toEqual([{ role: 'admin' }, { active: false }])
  })

  it('resets a password', async () => {
    const fetchMock = setup()
    const amina = await row('Amina Bello')
    await user.click(within(amina).getByRole('button', { name: 'Reset password' }))
    await user.type(within(amina).getByLabelText('Password'), 'Brand-new-pass-9')
    await user.type(within(amina).getByLabelText('Repeat password'), 'Brand-new-pass-9')
    await user.click(within(amina).getByRole('button', { name: 'Set password' }))
    expect(await screen.findByText('New password set for Amina Bello.')).toBeInTheDocument()
    expect(sentBodies(fetchMock, 'POST /users/amina/password')).toEqual([{ password: 'Brand-new-pass-9' }])
  })

  it('won’t let administrators change their own role or disable themselves', async () => {
    setup()
    const me = await row('Jubril Olalekan')
    expect(within(me).getByText('You')).toBeInTheDocument()
    expect(within(me).getByLabelText('Role for jubril')).toBeDisabled()
    expect(within(me).queryByRole('button', { name: /Disable/ })).not.toBeInTheDocument()
  })

  it('shows the server’s reason when a change is refused', async () => {
    setup({
      'PATCH /users/amina': () => reply(409, { detail: 'amina is the only active administrator' }),
    })
    const amina = await row('Amina Bello')
    await user.selectOptions(within(amina).getByLabelText('Role for amina'), 'analyst')
    expect(await screen.findByText(/Amina Bello: amina is the only active administrator/)).toBeInTheDocument()
  })
})
