import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockApi, sentBodies } from '../test/mockApi'
import PriorAuthListsCard from './PriorAuthListsCard'

const PAYERS = [
  { payer_id: 'PAY001', payer_name: 'Medicare FFS', payer_type: 'Medicare' },
  { payer_id: 'PAY010', payer_name: 'Self-Pay', payer_type: 'Self-Pay' },
]
const LIST = {
  payer_id: 'PAY001',
  cpt_codes: ['70553', '99213'],
  updated_at: '2026-11-01T10:00:00Z',
  updated_by: 'admin1',
}

describe('PriorAuthListsCard', () => {
  it('saves pasted codes for a payer, and never offers self-pay', async () => {
    const lists = []
    const fetchMock = mockApi({
      'GET /payers': () => PAYERS,
      'GET /organisation/prior-auth-lists': () => lists,
      'PUT /organisation/prior-auth-lists/PAY001': () => {
        lists.push(LIST)
        return LIST
      },
    })
    render(<PriorAuthListsCard />)
    const payer = await screen.findByLabelText('Payer')
    await screen.findByRole('option', { name: 'Medicare FFS' })
    expect(screen.queryByRole('option', { name: 'Self-Pay' })).not.toBeInTheDocument()
    await userEvent.selectOptions(payer, 'PAY001')
    await userEvent.type(screen.getByLabelText(/CPT or HCPCS/), '70553, 99213{enter}j1745 70553')
    await userEvent.click(screen.getByRole('button', { name: 'Save list (3)' }))
    expect(await screen.findByText(/2 services/)).toBeInTheDocument()
    expect(sentBodies(fetchMock, 'PUT /organisation/prior-auth-lists/PAY001')).toEqual([
      { cpt_codes: ['70553', '99213', 'J1745'] },
    ])
  })

  it('edits a list in place, and asks before removing one', async () => {
    let lists = [LIST]
    const fetchMock = mockApi({
      'GET /payers': () => PAYERS,
      'GET /organisation/prior-auth-lists': () => lists,
      'DELETE /organisation/prior-auth-lists/PAY001': () => {
        lists = []
        return null
      },
    })
    render(<PriorAuthListsCard />)
    await userEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    expect(screen.getByLabelText(/CPT or HCPCS/)).toHaveValue('70553\n99213')
    expect(screen.getByRole('button', { name: 'Replace list (2)' })).toBeEnabled()

    await userEvent.click(screen.getByRole('button', { name: 'Remove' }))
    await userEvent.click(screen.getByRole('button', { name: 'Keep it' }))
    expect(sentBodies(fetchMock, 'DELETE /organisation/prior-auth-lists/PAY001')).toEqual([])
    await userEvent.click(screen.getByRole('button', { name: 'Remove' }))
    await userEvent.click(screen.getByRole('button', { name: 'Yes, remove' }))
    expect(await screen.findByRole('button', { name: 'Save list (2)' })).toBeInTheDocument()
    expect(screen.queryByText('Medicare FFS', { selector: 'p' })).not.toBeInTheDocument()
  })
})
