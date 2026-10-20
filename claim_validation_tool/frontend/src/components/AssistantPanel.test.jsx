import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockApi, reply, sentBodies } from '../test/mockApi'
import AssistantPanel from './AssistantPanel'

const SOURCES = [
  {
    label: 'S1',
    source_type: 'carc',
    reference_id: '197',
    title: 'CARC 197: Precertification/authorization absent',
    excerpt: 'Claim Adjustment Reason Code 197: Precertification/authorization absent.',
    match_reason: 'On the claim’s denial',
    cited: true,
  },
  {
    label: 'S2',
    source_type: 'payer',
    reference_id: 'PAY002',
    title: 'Payer profile: Blue Cross NC',
    excerpt: 'Blue Cross NC (Commercial, PAY002)…',
    match_reason: 'The claim’s billed payer',
    cited: false,
  },
]

const FACTS = {
  payer_id: 'PAY002',
  payer_name: 'Blue Cross NC',
  claim_type: 'Institutional',
  place_of_service: '22',
  service_year: 2025,
  lines: [{ cpt_code: '43239', modifier: '59', units: 1, icd10_pointer: 'K21.0' }],
  denials: [{ carc_code: '197', rarc_code: 'N362' }],
}

const ANSWER = {
  question: 'Draft appeal wording for this denial based on its CARC/RARC codes and the claim.',
  answer: 'The denial is for **missing authorization** [S1].\n\n- Attach the approval [S1]',
  sources: SOURCES,
  mode: 'claude',
  model: 'claude-sonnet-5-5',
  notice: null,
  topic: 'appeal',
  claim_facts: FACTS,
}

describe('AssistantPanel', () => {
  it('starts from the topic’s question and sends it with the claim', async () => {
    const fetchMock = mockApi({ 'POST /assistant': () => ANSWER })
    render(<AssistantPanel claimId="CLM0000002" topic="appeal" />)
    expect(screen.getByLabelText(/Ask the assistant · Appeal wording/)).toHaveValue(ANSWER.question)
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    await screen.findByText('Claude · claude-sonnet-5-5')
    expect(sentBodies(fetchMock, 'POST /assistant')).toEqual([
      { question: ANSWER.question, claim_id: 'CLM0000002', topic: 'appeal' },
    ])
  })

  it('renders the answer with citations linked to its sources', async () => {
    mockApi({ 'POST /assistant': () => ANSWER })
    render(<AssistantPanel claimId="CLM0000002" topic="appeal" />)
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    expect(await screen.findByText('missing authorization')).toContainHTML('strong')
    const citations = screen.getAllByRole('link', { name: 'S1' })
    expect(citations).toHaveLength(2)
    const source = document.getElementById(citations[0].getAttribute('href').slice(1))
    expect(within(source).getByText('CARC 197: Precertification/authorization absent')).toBeInTheDocument()
    expect(screen.getByText('· not cited')).toBeInTheDocument() // S2
    expect(screen.getByText(/43239-59 ×1 → K21.0/)).toHaveTextContent('Codes and amounts only')
  })

  it('shows why Claude wasn’t used', async () => {
    mockApi({
      'POST /assistant': () => ({
        ...ANSWER,
        mode: 'retrieval',
        model: null,
        notice: 'Claude isn’t configured (no ANTHROPIC_API_KEY); showing the matching sources.',
      }),
    })
    render(<AssistantPanel claimId="CLM0000002" topic="appeal" />)
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    expect(await screen.findByText('Sources only')).toBeInTheDocument()
    expect(screen.getByText(/no ANTHROPIC_API_KEY/)).toBeInTheDocument()
    // The sources stand on their own: no repeated summary, nothing marked uncited
    expect(screen.queryByText('missing authorization')).not.toBeInTheDocument()
    expect(screen.queryByText('· not cited')).not.toBeInTheDocument()
    expect(screen.getByText('Payer profile: Blue Cross NC')).toBeInTheDocument()
  })

  it('reports a failed request', async () => {
    mockApi({ 'POST /assistant': () => reply(404, { detail: 'Claim CLM0000002 not found' }) })
    render(<AssistantPanel claimId="CLM0000002" topic="appeal" />)
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Claim CLM0000002 not found')
  })
})
