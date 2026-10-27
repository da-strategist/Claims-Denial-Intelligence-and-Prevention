import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { AuthContext } from '../hooks/useAuth'
import { mockApi, reply } from '../test/mockApi'
import ClaimsWorkbench from './ClaimsWorkbench'

const CLAIM = {
  claim_id: 'CLM0000002',
  patient_id: 'PAT000002',
  payer_id: 'PAY001',
  service_date: '2025-03-01',
  claim_type: 'Professional',
  status: 'Denied',
  total_charge: 1200,
  total_paid: 0,
  days_in_ar: 40,
}

const page = (items, total = items.length) => ({ items, total, page: 1, pages: 1, page_size: 25 })

function setup() {
  const fetchMock = mockApi({
    'GET /claims': ({ params }) => (params.page_size === '1' ? page([], 7) : page([CLAIM])),
    'POST /validate': () => [{ claim_id: CLAIM.claim_id, status: 'error', risk_score: 75, findings: [], risk_factors: [] }],
    'GET /payers': () => [{ payer_id: 'PAY001', payer_name: 'Aetna' }],
    'GET /departments': () => [{ department_id: 'DEP001', department_name: 'Cardiology' }],
  })
  const listCalls = () =>
    fetchMock.mock.calls
      .map(([url]) => new URL(url, 'http://localhost'))
      .filter((url) => url.pathname === '/api/claims' && url.searchParams.get('page_size') !== '1')
      .map((url) => Object.fromEntries(url.searchParams))
  return { listCalls }
}

describe('ClaimsWorkbench', () => {
  beforeEach(() => {
    window.location.hash = '#/claims'
  })

  it('opens on the claims that need attention, riskiest first', async () => {
    const { listCalls } = setup()
    render(<ClaimsWorkbench />)
    expect(await screen.findByText('CLM0000002')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Needs attention/ })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: /Needs attention/ })).toHaveTextContent('7')
    expect(listCalls().at(-1)).toMatchObject({ needs_attention: 'true', sort_by: 'risk_score', sort_desc: 'true' })

    await userEvent.click(screen.getByRole('tab', { name: 'All claims' }))
    await waitFor(() => expect(listCalls().at(-1).needs_attention).toBeUndefined())
    expect(listCalls().at(-1)).toMatchObject({ sort_by: 'service_date' })
  })

  it('shows a linked claim whatever its validation result', async () => {
    window.location.hash = '#/claims?search=CLM0000002'
    const { listCalls } = setup()
    render(<ClaimsWorkbench />)
    expect(await screen.findByText('CLM0000002')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'All claims' })).toHaveAttribute('aria-selected', 'true')
    expect(listCalls().at(-1)).toMatchObject({ search: 'CLM0000002' })
  })

  it('keeps the dashboard period as a removable filter', async () => {
    window.location.hash = '#/claims?attention=1&from=2025-01-01&to=2025-12-31&department_id=DEP001'
    const { listCalls } = setup()
    render(<ClaimsWorkbench />)
    await screen.findByText('CLM0000002')
    expect(listCalls().at(-1)).toMatchObject({
      needs_attention: 'true',
      service_date_from: '2025-01-01',
      service_date_to: '2025-12-31',
      department_id: 'DEP001',
    })

    await userEvent.click(await screen.findByRole('button', { name: 'Remove filter: Cardiology' }))
    await waitFor(() => expect(listCalls().at(-1).department_id).toBeUndefined())
  })

  it('points to All claims when the queue is empty but the filters match claims there', async () => {
    // A pending claim passed every rule (it couldn't be submitted otherwise), so it's never queued
    const pending = { ...CLAIM, status: 'Pending' }
    mockApi({
      'GET /claims': ({ params }) =>
        params.needs_attention === 'true' ? page([], 0) : page([pending]),
      'POST /validate': () => [{ claim_id: CLAIM.claim_id, status: 'pass', risk_score: 0, findings: [], risk_factors: [] }],
      'GET /payers': () => [{ payer_id: 'PAY001', payer_name: 'Aetna' }],
      'GET /departments': () => [],
    })
    render(<ClaimsWorkbench />)
    await userEvent.selectOptions(await screen.findByLabelText('Claim status'), 'Pending')
    expect(await screen.findByText(/None of these need attention, but/)).toHaveTextContent('1 claim matches these filters')
    await userEvent.click(screen.getByRole('button', { name: 'Show it in All claims' }))
    expect(await screen.findByText('CLM0000002')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'All claims' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByLabelText('Claim status')).toHaveValue('Pending')  // the filter carries over
  })

  it('keeps a fixed claim open until it is collapsed, though it leaves the queue', async () => {
    const finding = {
      rule_id: 'RULE-002',
      rule_name: 'Missing Prior Authorization',
      category: 'Authorization',
      severity: 'error',
      message: 'No prior authorization number',
    }
    const before = { claim_id: CLAIM.claim_id, status: 'error', risk_score: 75, findings: [finding], risk_factors: [] }
    const after = { claim_id: CLAIM.claim_id, status: 'pass', risk_score: 10, findings: [], risk_factors: [] }
    const suggestion = {
      id: `${CLAIM.claim_id}:RULE-002`,
      claim_id: CLAIM.claim_id,
      rule_id: 'RULE-002',
      title: 'Add the authorization number',
      summary: 'Enter the number from the payer.',
      reasoning: 'The payer requires it.',
      steps: [],
      action: 'apply',
      confidence: 'high',
      changes: [{ field: 'prior_auth_number', label: 'Authorization number', type: 'text', current_value: null, suggested_value: 'PA123' }],
      citations: [],
      clarification_topic: null,
      needs_clarification: false,
    }
    let fixed = false
    let listed = 0
    const fixes = () => ({ suggestions: fixed ? [] : [suggestion], corrections: [], validation: fixed ? after : before })
    mockApi({
      // Once fixed, the claim no longer needs attention
      'GET /claims': ({ params }) => (params.page_size === '1' ? page([], fixed ? 0 : 1) : (listed++, page(fixed ? [] : [CLAIM]))),
      'POST /validate': () => [fixed ? after : before],
      'GET /payers': () => [{ payer_id: 'PAY001', payer_name: 'Aetna' }],
      'GET /departments': () => [],
      [`GET /claims/${CLAIM.claim_id}`]: () => reply(404, { detail: 'not in this test' }),
      [`GET /aifix/${CLAIM.claim_id}`]: fixes,
      [`POST /aifix/${CLAIM.claim_id}/apply`]: () => {
        fixed = true
        const applied = [{ id: 'C1', claim_id: CLAIM.claim_id, field: 'prior_auth_number', old_value: null, new_value: 'PA123', suggestion_id: suggestion.id, applied_at: '2026-10-27T10:00:00Z' }]
        return { claim_id: CLAIM.claim_id, applied, before, after: fixes() }
      },
    })
    const biller = { user: { username: 'biller1', permissions: ['claims:read', 'claims:write'] } }
    render(
      <AuthContext.Provider value={biller}>
        <ClaimsWorkbench />
      </AuthContext.Provider>,
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Expand claim CLM0000002' }))
    const apply = await screen.findByRole('button', { name: /Apply fix & re-validate/ })
    const listedBefore = listed
    await userEvent.click(apply)
    await waitFor(() => expect(listed).toBeGreaterThan(listedBefore))
    expect(screen.getByText('CLM0000002')).toBeInTheDocument()
    expect(screen.getByText(/Fix applied/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Collapse claim CLM0000002' }))
    await waitFor(() => expect(screen.queryByText('CLM0000002')).not.toBeInTheDocument())
  })
})
