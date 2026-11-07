import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockApi, reply, sentBodies } from '../test/mockApi'
import ApiKeysCard from './ApiKeysCard'

const KEY = {
  id: 'ab12cd34',
  name: 'Epic test',
  created_at: '2026-11-01T10:00:00Z',
  created_by: 'admin1',
  last_used_at: null,
  revoked_at: null,
  revoked_by: null,
}

describe('ApiKeysCard', () => {
  it('shows a new key once, until it is dismissed', async () => {
    const keys = []
    const fetchMock = mockApi({
      'GET /organisation/api-keys': () => keys,
      'POST /organisation/api-keys': () => {
        keys.push(KEY)
        return { key: KEY, token: 'crcm_ab12cd34_secret' }
      },
    })
    render(<ApiKeysCard />)
    const create = await screen.findByRole('button', { name: 'Create key' })
    expect(create).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/which system/i), '  Epic test ')
    await userEvent.click(create)
    expect(await screen.findByText('crcm_ab12cd34_secret')).toBeInTheDocument()
    expect(sentBodies(fetchMock, 'POST /organisation/api-keys')).toEqual([{ name: 'Epic test' }])
    expect(await screen.findByText(/Not used yet/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /saved it/ }))
    expect(screen.queryByText('crcm_ab12cd34_secret')).not.toBeInTheDocument()
  })

  it('asks before revoking, and can be talked out of it', async () => {
    let current = KEY
    const fetchMock = mockApi({
      'GET /organisation/api-keys': () => [current],
      'DELETE /organisation/api-keys/ab12cd34': () => {
        current = { ...KEY, revoked_at: '2026-11-02T10:00:00Z', revoked_by: 'admin1' }
        return current
      },
    })
    render(<ApiKeysCard />)
    await userEvent.click(await screen.findByRole('button', { name: 'Revoke' }))
    await userEvent.click(screen.getByRole('button', { name: 'Keep it' }))
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'DELETE')).toHaveLength(0)
    await userEvent.click(screen.getByRole('button', { name: 'Revoke' }))
    await userEvent.click(screen.getByRole('button', { name: 'Yes, revoke' }))
    expect(await screen.findByText(/Revoked/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Revoke' })).not.toBeInTheDocument()
  })

  it('says why a key could not be created', async () => {
    mockApi({
      'GET /organisation/api-keys': () => [],
      'POST /organisation/api-keys': () => reply(409, { detail: "There's already an active key named Epic" }),
    })
    render(<ApiKeysCard />)
    await userEvent.type(await screen.findByLabelText(/which system/i), 'Epic')
    await userEvent.click(screen.getByRole('button', { name: 'Create key' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not create the key')
  })
})
