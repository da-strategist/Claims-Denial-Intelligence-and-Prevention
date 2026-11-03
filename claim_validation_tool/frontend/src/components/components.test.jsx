import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { mockApi, reply, sentBodies } from '../test/mockApi'
import FixSuggestion from './FixSuggestion'
import Pagination from './Pagination'
import RiskScore from './RiskScore'
import { ClaimStatusBadge, ValidationBadge } from './StatusBadge'
import SubmitClaim from './SubmitClaim'
import { AuthContext } from '../hooks/useAuth'
import EdiFileCard from './EdiFileCard'

describe('badges and scores', () => {
  it('shows the overdue flag next to the claim status', () => {
    render(<ClaimStatusBadge status="Pending" overdue />)
    expect(screen.getByText('Pending')).toBeInTheDocument()
    expect(screen.getByText('Overdue')).toHaveAttribute(
      'title',
      expect.stringContaining('average days to pay'),
    )
  })

  it('shows a dash for unknown validation results and scores', () => {
    const { container } = render(
      <>
        <ValidationBadge status="aifix" />
        <ValidationBadge status={undefined} />
        <RiskScore score={null} />
      </>,
    )
    expect(screen.getByText('AI Fix')).toBeInTheDocument()
    expect(container).toHaveTextContent(/—.*—/)
  })

  it.each([
    [10, 'Low risk'],
    [30, 'Medium risk'],
    [60, 'High risk'],
  ])('rates a score of %i as %s', (score, title) => {
    render(<RiskScore score={score} />)
    expect(screen.getByTitle(title)).toHaveTextContent(String(score))
  })
})

describe('Pagination', () => {
  it('shows the range and disables moves past either end', async () => {
    const onPageChange = vi.fn()
    render(<Pagination page={1} pages={3} total={120} pageSize={50} onPageChange={onPageChange} />)
    expect(screen.getByText('Showing 1–50 of 120')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(onPageChange).toHaveBeenCalledWith(2)
  })

  it('handles an empty result', () => {
    render(<Pagination page={1} pages={0} total={0} pageSize={50} onPageChange={() => {}} />)
    expect(screen.getByText('Showing 0–0 of 0')).toBeInTheDocument()
    expect(screen.getByText('Page 1 of 1')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
  })
})

describe('SubmitClaim', () => {
  const draft = { claim_id: 'CLM0120001', status: 'Draft' }

  it('is only offered for drafts', () => {
    const { container } = render(
      <SubmitClaim claim={{ ...draft, status: 'Pending' }} validation={{ status: 'pass' }} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it.each(['error', 'aifix', 'warning'])('is blocked while a rule %s remains', (status) => {
    render(<SubmitClaim claim={draft} validation={{ status }} />)
    expect(screen.getByRole('button', { name: 'Mark as submitted' })).toBeDisabled()
    expect(screen.getByText('Resolve every error and warning before submitting.')).toBeInTheDocument()
  })

  it('submits a claim that passes and hands back the pending claim', async () => {
    const pending = { claim: { ...draft, status: 'Pending' }, validation: { status: 'pass' } }
    mockApi({ 'POST /claims/CLM0120001/submit': () => pending })
    const onSubmitted = vi.fn()
    render(<SubmitClaim claim={draft} validation={{ status: 'pass' }} onSubmitted={onSubmitted} />)
    await userEvent.click(screen.getByRole('button', { name: 'Mark as submitted' }))
    expect(onSubmitted).toHaveBeenCalledWith(pending)
  })

  it('offers the billing system first by default, and lets open issues go there once acknowledged', async () => {
    const handedOff = { claim: { ...draft, status: 'Handed off' }, validation: { status: 'error' } }
    const fetchMock = mockApi({ 'POST /claims/CLM0120001/hand-off': () => handedOff })
    const onSubmitted = vi.fn()
    render(<SubmitClaim claim={draft} validation={{ status: 'error' }} onSubmitted={onSubmitted} />)
    const [first, second] = screen.getAllByRole('button')
    expect(first).toHaveTextContent('Hand off to billing system')
    expect(second).toHaveTextContent('Mark as submitted')
    expect(first).toBeDisabled()
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(first)
    expect(onSubmitted).toHaveBeenCalledWith(handedOff)
    expect(sentBodies(fetchMock, 'POST /claims/CLM0120001/hand-off')).toEqual([{ acknowledge_open_issues: true }])
  })

  it('puts sending first when that is the organisation default', () => {
    render(
      <AuthContext.Provider value={{ user: { organisation: { default_claim_route: 'send' } } }}>
        <SubmitClaim claim={draft} validation={{ status: 'pass' }} />
      </AuthContext.Provider>,
    )
    expect(screen.getAllByRole('button')[0]).toHaveTextContent('Mark as submitted')
  })

  it('only reopens a handed-off claim once someone confirms it was not sent', async () => {
    const handedOff = {
      ...draft,
      status: 'Handed off',
      handoff: { handed_off_on: '2026-11-03', handed_off_by: 'jubril', open_issues: ['RULE-002 Missing Prior Authorization'] },
    }
    const reopened = { claim: draft, validation: { status: 'pass' } }
    mockApi({
      'POST /claims/CLM0120001/reopen': () => reopened,
      'GET /claims/CLM0120001/handoff': () => ({ claim_id: 'CLM0120001', source_ref: null, changes: [], open_issues: [], edi: null }),
    })
    const onSubmitted = vi.fn()
    render(<SubmitClaim claim={handedOff} validation={{ status: 'pass' }} onSubmitted={onSubmitted} />)
    expect(screen.getByText('RULE-002 Missing Prior Authorization')).toBeInTheDocument()
    await screen.findByText('Nothing was changed here.')
    expect(screen.queryByRole('button', { name: 'Mark as submitted' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Reopen claim' }))
    const confirm = screen.getByRole('button', { name: 'Reopen as draft' })
    expect(confirm).toBeDisabled()
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(confirm)
    expect(onSubmitted).toHaveBeenCalledWith(reopened)
  })

  it('offers a handed-off claim’s 837 and list of changes, and says when it’s a test file', async () => {
    const handedOff = {
      ...draft,
      status: 'Handed off',
      handoff: { handed_off_on: '2026-11-03', handed_off_by: 'jubril', open_issues: [] },
    }
    mockApi({
      'GET /claims/CLM0120001/handoff': () => ({
        claim_id: 'CLM0120001',
        source_ref: 'HOSP-77',
        open_issues: [],
        edi: { transaction: '837P', control_number: '000000000', generated_at: '2026-11-03T10:00:00', test: true, notes: ['Not set: submitter ID'] },
        changes: [
          {
            field: 'pa_number',
            label: 'Prior auth number',
            old_value: null,
            new_value: 'PA123',
            source: 'AI Fix',
            changed_by: 'jubril',
            changed_at: '2026-11-03T09:00:00Z',
          },
        ],
      }),
    })
    render(<SubmitClaim claim={handedOff} validation={{ status: 'pass' }} onSubmitted={vi.fn()} />)
    expect(await screen.findByText('Prior auth number: — → PA123')).toBeInTheDocument()
    expect(screen.getByText('Your claim number: HOSP-77')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Download 837P' })).toHaveAttribute('href', '/api/claims/CLM0120001/handoff/837')
    expect(screen.getByRole('link', { name: 'List of changes (PDF)' })).toHaveAttribute('href', '/api/claims/CLM0120001/handoff/changes.pdf')
    expect(screen.getByText(/marked as a test file.*submitter ID/)).toBeInTheDocument()
  })

  it('has only the list of changes for a self-pay claim', async () => {
    const handedOff = { ...draft, status: 'Handed off', handoff: { handed_off_on: '2026-11-03', handed_off_by: 'jubril', open_issues: [] } }
    mockApi({
      'GET /claims/CLM0120001/handoff': () => ({ claim_id: 'CLM0120001', source_ref: null, changes: [], open_issues: [], edi: null }),
    })
    render(<SubmitClaim claim={handedOff} validation={{ status: 'pass' }} onSubmitted={vi.fn()} />)
    expect(await screen.findByText(/billed to the patient/)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Download/ })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'List of changes (PDF)' })).toBeInTheDocument()
  })

  it('shows why the server refused', async () => {
    mockApi({
      'POST /claims/CLM0120001/submit': () =>
        reply(409, { detail: "A claim can't be submitted before its service date" }),
    })
    render(<SubmitClaim claim={draft} validation={{ status: 'pass' }} onSubmitted={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Mark as submitted' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('before its service date')
  })
})

describe('FixSuggestion', () => {
  const suggestion = {
    id: 'CLM0000002:RULE-002',
    claim_id: 'CLM0000002',
    action: 'apply',
    confidence: 'high',
    title: 'Record the prior authorization',
    summary: 'Blue Cross NC requires prior authorization.',
    reasoning: 'Claims without it are denied.',
    steps: ['Find the auth number'],
    citations: [
      {
        source_type: 'payer',
        reference_id: 'PAY002',
        title: 'Blue Cross NC',
        excerpt: 'PA strictness 0.5',
      },
    ],
    changes: [
      {
        field: 'pa_obtained',
        label: 'Prior Auth Obtained',
        type: 'boolean',
        current_value: 'false',
        suggested_value: 'true',
      },
      {
        field: 'pa_number',
        label: 'Prior Auth Number',
        type: 'string',
        current_value: '',
        suggested_value: null,
        requires_input: true,
      },
    ],
    needs_clarification: false,
  }

  it('sends only the fields the specialist can edit', async () => {
    const onApply = vi.fn().mockResolvedValue()
    render(<FixSuggestion suggestion={suggestion} onApply={onApply} />)
    await userEvent.type(screen.getByLabelText(/Prior Auth Number/), 'AUTH-42')
    await userEvent.click(screen.getByRole('button', { name: 'Apply fix & re-validate' }))
    expect(onApply).toHaveBeenCalledWith(suggestion, { pa_number: 'AUTH-42' })
  })

  it('shows a refused fix and lets the specialist retry', async () => {
    const onApply = vi.fn().mockRejectedValue(new Error('Prior Auth Number is required'))
    render(<FixSuggestion suggestion={suggestion} onApply={onApply} />)
    await userEvent.click(screen.getByRole('button', { name: 'Apply fix & re-validate' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Prior Auth Number is required')
    expect(screen.getByRole('button', { name: 'Apply fix & re-validate' })).toBeEnabled()
  })

  it('opens the assistant for suggestions that need clarification', async () => {
    const appeal = {
      ...suggestion,
      action: 'clarify',
      clarification_topic: 'appeal',
      needs_clarification: true,
    }
    render(<FixSuggestion suggestion={appeal} onApply={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Ask the assistant' }))
    expect(screen.getByRole('region', { name: 'Clarification assistant' })).toBeInTheDocument()
  })

  it('is read-only for roles that cannot change claims', () => {
    render(<FixSuggestion suggestion={suggestion} onApply={null} />)
    expect(screen.queryByRole('button', { name: /Apply fix/ })).not.toBeInTheDocument()
    expect(screen.getByText('Your role can view this fix but not apply it.')).toBeInTheDocument()
  })

  it('has no form for manual suggestions', () => {
    render(<FixSuggestion suggestion={{ ...suggestion, action: 'manual' }} onApply={vi.fn()} />)
    expect(screen.queryByRole('button', { name: /Apply fix/ })).not.toBeInTheDocument()
    expect(screen.getByText('Find the auth number')).toBeInTheDocument()
  })
})

describe('EdiFileCard', () => {
  const edi = {
    transaction: '837P',
    control_number: '000000007',
    generated_at: '2026-10-17T10:00:00',
    test: true,
    notes: ['Not set: billing provider NPI, submitter ID', 'Settings mode is test'],
  }
  const renderAs = (permissions) =>
    render(
      <AuthContext.Provider value={{ user: { permissions } }}>
        <EdiFileCard claimId="CLM0120001" edi={edi} />
      </AuthContext.Provider>,
    )

  it('marks a test file, says what’s missing, and offers the download to billers', () => {
    renderAs(['claims:read', 'claims:write'])
    expect(screen.getByText('Test file')).toBeInTheDocument()
    expect(screen.getByText(/billing provider NPI, submitter ID/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Download 837' })).toHaveAttribute('href', '/api/claims/CLM0120001/837')
    expect(screen.getByRole('link', { name: 'CMS-1500 PDF' })).toHaveAttribute('href', '/api/claims/CLM0120001/claim-form.pdf')
    expect(screen.getByRole('link', { name: 'Readable 837 PDF' })).toHaveAttribute('href', '/api/claims/CLM0120001/837-readable.pdf')
  })

  it('has no download for roles that can’t change claims', () => {
    renderAs(['claims:read'])
    expect(screen.queryAllByRole('link')).toHaveLength(0)
  })
})
