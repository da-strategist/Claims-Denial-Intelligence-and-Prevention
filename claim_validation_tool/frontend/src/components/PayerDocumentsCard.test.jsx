import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockApi, reply, sentBodies } from '../test/mockApi'
import PayerDocumentsCard from './PayerDocumentsCard'
import RuleBuilder from './RuleBuilder'
import RuleSourceLink from './RuleSourceLink'

const PAYERS = {
  PAY001: { payer_id: 'PAY001', payer_name: 'Medicare FFS', payer_type: 'Medicare' },
  PAY010: { payer_id: 'PAY010', payer_name: 'Self-Pay', payer_type: 'Self-Pay' },
}
const DOCUMENT = {
  id: 'DOC-001',
  payer_id: 'PAY001',
  title: 'Provider manual 2026',
  effective_date: '2026-01-01',
  filename: 'manual.pdf',
  media_type: 'application/pdf',
  size_bytes: 2048,
  pages: 12,
  pages_with_text: 12,
  uploaded_at: '2026-11-01T10:00:00Z',
  uploaded_by: 'admin1',
}

describe('PayerDocumentsCard', () => {
  it('uploads a file for a payer, never offering self-pay', async () => {
    const fetchMock = mockApi({ 'POST /payer-documents': () => DOCUMENT })
    let reloaded = 0
    render(<PayerDocumentsCard documents={[]} payers={PAYERS} rules={[]} reload={() => reloaded++} />)
    expect(screen.getByText('No documents yet.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Add document' }))
    expect(screen.queryByRole('option', { name: 'Self-Pay' })).not.toBeInTheDocument()

    const file = new File(['%PDF-1.4 manual'], 'Medicare manual.pdf', { type: 'application/pdf' })
    await userEvent.upload(screen.getByLabelText(/^File/), file)
    expect(screen.getByLabelText('Title')).toHaveValue('Medicare manual')
    await userEvent.selectOptions(screen.getByLabelText('Payer'), 'PAY001')
    await userEvent.type(screen.getByLabelText(/Effective date/), '2026-01-01')
    await userEvent.click(screen.getByRole('button', { name: 'Upload document' }))

    await screen.findByRole('button', { name: 'Add document' })
    const [sent] = sentBodies(fetchMock, 'POST /payer-documents')
    expect(sent).toMatchObject({
      payer_id: 'PAY001',
      title: 'Medicare manual',
      effective_date: '2026-01-01',
      filename: 'Medicare manual.pdf',
    })
    expect(atob(sent.content)).toBe('%PDF-1.4 manual')
    expect(reloaded).toBe(1)
  })

  it('lists documents with the rules citing them, and explains a refused delete', async () => {
    mockApi({
      'DELETE /payer-documents/DOC-001': () =>
        reply(409, { detail: 'RULE-012 cites this document. Remove it from the rule’s source first.' }),
    })
    const rules = [{ id: 'RULE-012', source: { document_id: 'DOC-001', page: 4 } }]
    render(<PayerDocumentsCard documents={[DOCUMENT]} payers={PAYERS} rules={rules} reload={() => {}} />)
    expect(screen.getByText(/Medicare FFS · 12 pages/)).toBeInTheDocument()
    expect(screen.getByText('Cited by RULE-012')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Download' })).toHaveAttribute('href', '/api/payer-documents/DOC-001/file')

    await userEvent.click(screen.getByRole('button', { name: 'Delete Provider manual 2026' }))
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('RULE-012 cites this document')
  })

  it('warns when nothing could be read from a document', () => {
    render(
      <PayerDocumentsCard
        documents={[{ ...DOCUMENT, pages_with_text: 0 }]}
        payers={PAYERS}
        rules={[]}
        reload={() => {}}
      />,
    )
    expect(screen.getByText(/assistant can’t search it/)).toBeInTheDocument()
  })
})

describe('citing a document in a rule', () => {
  const FIELDS = {
    total_charge: { field: 'total_charge', label: 'Total Charge', type: 'number', operators: ['greaterThan'] },
  }

  it('saves the document, page and passage with the rule', async () => {
    const fetchMock = mockApi({
      'GET /payer-documents/DOC-001/pages/4': () => ({ document_id: 'DOC-001', page: 4, pages: 12, text: 'MRI needs prior authorization.' }),
      'POST /rules': ({ body }) => ({ ...body, id: 'RULE-020' }),
    })
    render(
      <RuleBuilder
        rule={null}
        fields={FIELDS}
        payers={PAYERS}
        departments={{}}
        documents={[DOCUMENT]}
        onClose={() => {}}
        onSaved={() => {}}
      />,
    )
    await userEvent.type(screen.getByLabelText('Name'), 'Medicare MRI authorization')
    await userEvent.selectOptions(screen.getByLabelText('Category'), 'Payer-Specific')
    await userEvent.type(screen.getByLabelText('Condition 1 value'), '0')
    await userEvent.selectOptions(screen.getByLabelText(/Payer document/), 'DOC-001')
    const page = screen.getByLabelText('Page')
    await userEvent.clear(page)
    await userEvent.type(page, '4')
    await userEvent.click(screen.getByRole('button', { name: 'Show its text' }))
    expect(await screen.findByText('MRI needs prior authorization.')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText(/Passage/), 'MRI needs prior authorization.')
    await userEvent.click(screen.getByRole('button', { name: 'Create rule' }))

    const [sent] = sentBodies(fetchMock, 'POST /rules')
    expect(sent.source).toEqual({ document_id: 'DOC-001', page: 4, excerpt: 'MRI needs prior authorization.' })
  })

  it('sends no source when none is chosen', async () => {
    const fetchMock = mockApi({ 'POST /rules': ({ body }) => ({ ...body, id: 'RULE-021' }) })
    render(
      <RuleBuilder rule={null} fields={FIELDS} payers={PAYERS} departments={{}} documents={[]} onClose={() => {}} onSaved={() => {}} />,
    )
    expect(screen.getByText(/No payer documents yet/)).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Name'), 'Large charge')
    await userEvent.selectOptions(screen.getByLabelText('Category'), 'Billing')
    await userEvent.type(screen.getByLabelText('Condition 1 value'), '5000')
    await userEvent.click(screen.getByRole('button', { name: 'Create rule' }))
    expect(sentBodies(fetchMock, 'POST /rules')[0].source).toBeNull()
  })

  it('links a source to its document', () => {
    render(<RuleSourceLink source={{ document_id: 'DOC-001', document_title: 'Provider manual 2026', page: 4 }} />)
    const link = within(screen.getByText(/Source:/)).getByRole('link')
    expect(link).toHaveTextContent('Provider manual 2026, page 4')
    expect(link).toHaveAttribute('href', '/api/payer-documents/DOC-001/file')
  })
})
