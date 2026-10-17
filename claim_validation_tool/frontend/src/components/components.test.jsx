import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { mockApi, reply } from '../test/mockApi'
import FixSuggestion from './FixSuggestion'
import Pagination from './Pagination'
import RiskScore from './RiskScore'
import { ClaimStatusBadge, ValidationBadge } from './StatusBadge'
import SubmitClaim from './SubmitClaim'

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

  it('is blocked while rule errors remain', () => {
    render(<SubmitClaim claim={draft} validation={{ status: 'error' }} />)
    expect(screen.getByRole('button', { name: 'Mark as submitted' })).toBeDisabled()
    expect(screen.getByText('Resolve the rule errors before submitting.')).toBeInTheDocument()
  })

  it('submits and hands back the pending claim', async () => {
    const pending = { claim: { ...draft, status: 'Pending' }, validation: { status: 'warning' } }
    mockApi({ 'POST /claims/CLM0120001/submit': () => pending })
    const onSubmitted = vi.fn()
    render(
      <SubmitClaim claim={draft} validation={{ status: 'warning' }} onSubmitted={onSubmitted} />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Mark as submitted' }))
    expect(onSubmitted).toHaveBeenCalledWith(pending)
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

  it('has no form for manual suggestions', () => {
    render(<FixSuggestion suggestion={{ ...suggestion, action: 'manual' }} onApply={vi.fn()} />)
    expect(screen.queryByRole('button', { name: /Apply fix/ })).not.toBeInTheDocument()
    expect(screen.getByText('Find the auth number')).toBeInTheDocument()
  })
})
