import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockApi, reply, sentBodies } from '../test/mockApi'
import EdiSettingsCard from './EdiSettingsCard'

const BLANK = {
  mode: 'test',
  submitter: { id: '', name: '', contact_name: '', phone: '' },
  receiver: { id: '', name: '' },
  billing_provider: { name: '', npi: '', tax_id: '', address: { line1: '', city: '', state: '', zip_code: '' } },
  payer_ids: {},
  facility_zip_codes: {},
}
const status = (settings, handoff, sending) => ({
  settings,
  missing_for_handoff: handoff,
  missing_for_sending: sending,
})

function setup(handlers = {}) {
  const fetchMock = mockApi({
    'GET /organisation/edi-settings': () => status(BLANK, ['submitter ID'], ['submitter ID', 'clearinghouse name']),
    'GET /payers': () => [
      { payer_id: 'PAY001', payer_name: 'Medicare FFS', payer_type: 'Medicare' },
      { payer_id: 'PAY009', payer_name: 'Self-Pay', payer_type: 'Self-Pay' },
    ],
    'GET /facilities': () => [
      { facility_id: 'FAC001', facility_name: 'Main Campus', address: '1 Main St, Charlotte, NC 28211', status: 'Active' },
    ],
    ...handlers,
  })
  render(<EdiSettingsCard />)
  return fetchMock
}

describe('EdiSettingsCard', () => {
  it('says what each kind of file still needs, with no clearinghouse for the billing system', async () => {
    setup()
    expect(await screen.findByText('Still needed: submitter ID.')).toBeInTheDocument()
    expect(screen.getByText('Still needed: submitter ID, clearinghouse name.')).toBeInTheDocument()
  })

  it('saves what was entered, and leaves self-pay out of the payer IDs', async () => {
    const live = { ...BLANK, mode: 'production' }
    let saved = false
    const fetchMock = setup({
      'GET /organisation/edi-settings': () =>
        saved ? status(live, [], ['clearinghouse name']) : status(BLANK, ['submitter ID'], ['submitter ID']),
      'PUT /organisation/edi-settings': () => {
        saved = true
        return status(live, [], ['clearinghouse name'])
      },
    })
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Edit settings' }))
    const form = screen.getByRole('form', { name: 'Claim file settings' })
    await user.type(within(form).getByLabelText('Submitter ID'), 'SUB123')
    await user.type(await within(form).findByLabelText('Medicare FFS'), 'MCR01')
    await user.type(await within(form).findByLabelText(/Main Campus/), '282111234')
    expect(within(form).queryByLabelText('Self-Pay')).not.toBeInTheDocument()
    await user.click(within(form).getByLabelText(/Live files/))
    await user.click(within(form).getByRole('button', { name: 'Save settings' }))

    expect(await screen.findByText('Live')).toBeInTheDocument()
    expect(screen.queryByRole('form', { name: 'Claim file settings' })).not.toBeInTheDocument()
    const [body] = sentBodies(fetchMock, 'PUT /organisation/edi-settings')
    expect(body.mode).toBe('production')
    expect(body.submitter.id).toBe('SUB123')
    expect(body.payer_ids).toEqual({ PAY001: 'MCR01' })
    expect(body.facility_zip_codes).toEqual({ FAC001: '282111234' })
  })

  it('keeps the form open and says why when a save is refused', async () => {
    setup({ 'PUT /organisation/edi-settings': () => reply(422, { detail: 'Submitter phone needs 10 digits' }) })
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Edit settings' }))
    await user.click(screen.getByRole('button', { name: 'Save settings' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Submitter phone needs 10 digits')
    expect(screen.getByRole('form', { name: 'Claim file settings' })).toBeInTheDocument()
  })
})
