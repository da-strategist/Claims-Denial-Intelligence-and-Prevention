import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AuthContext } from '../hooks/useAuth'
import { mockApi } from '../test/mockApi'
import Dashboard from './Dashboard'

const kpi = (key, value, extra = {}) => ({
  key,
  label: key,
  value,
  format: 'count',
  previous: null,
  higher_is_better: null,
  detail: null,
  ...extra,
})

const DASHBOARD = (drafts) => ({
  period: { start: '2025-01-01', end: '2025-12-31' },
  comparison_period: null,
  data_range: { start: '2025-01-01', end: '2025-12-31' },
  kpis: [kpi('claims', 10), kpi('at_risk', 4, { detail: '3 of them have an AI fix ready' })],
  revenue_trend: [],
  denial_reasons: [],
  ar_aging: [],
  validation_status: [],
  payers: [],
  drafts,
})

function renderAs(permissions, drafts) {
  mockApi({
    'GET /dashboard': () => DASHBOARD(drafts),
    'GET /payers': () => [],
    'GET /departments': () => [],
  })
  render(
    <AuthContext.Provider value={{ user: { display_name: 'Test biller', permissions } }}>
      <Dashboard />
    </AuthContext.Provider>,
  )
}

const BILLER = ['claims:read', 'claims:write']

describe('Overview: needs attention and draft claims', () => {
  it('lists draft claims apart, with a link to finish them on New Claim', async () => {
    renderAs(BILLER, { claims: 3, with_problems: 2 })
    expect(await screen.findByText('3 draft claims to finish, 2 with problems')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open drafts' })).toHaveAttribute('href', '#/new-claim')
    expect(screen.getByRole('link', { name: 'Review claims' })).toBeInTheDocument()
  })

  it('says when every draft is ready to submit', async () => {
    renderAs(BILLER, { claims: 1, with_problems: 0 })
    expect(await screen.findByText('1 draft claim ready to submit')).toBeInTheDocument()
  })

  it('shows nothing when there are no drafts', async () => {
    renderAs(BILLER, { claims: 0, with_problems: 0 })
    await screen.findByRole('link', { name: 'Review claims' })
    expect(screen.queryByRole('link', { name: 'Open drafts' })).not.toBeInTheDocument()
  })

  it('hides the line from analysts', async () => {
    renderAs(['claims:read'], { claims: 3, with_problems: 2 })
    await screen.findByRole('link', { name: 'Review claims' })
    expect(screen.queryByText(/draft claims to finish/)).not.toBeInTheDocument()
  })
})
