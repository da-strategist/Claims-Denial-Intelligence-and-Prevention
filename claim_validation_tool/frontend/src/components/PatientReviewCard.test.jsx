import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockApi, reply } from '../test/mockApi'
import PatientReviewCard from './PatientReviewCard'

const ITEM = {
  patient_id: 'PAT000101',
  first_name: 'Amara',
  last_name: 'Okafor',
  birth_date: '1985-07-01',
  possible_matches: [{ patient_id: 'PAT000100', first_name: 'Amara', last_name: 'Okafor', birth_date: '1990-03-14' }],
}

describe('PatientReviewCard', () => {
  it('shows who to compare, and stops showing them once checked', async () => {
    let items = [ITEM]
    mockApi({
      'GET /patients/to-review': () => items,
      'POST /patients/PAT000101/not-a-duplicate': () => {
        items = []
        return reply(204)
      },
    })
    render(<PatientReviewCard />)
    expect(await screen.findByText(/1 patient to check/)).toBeInTheDocument()
    expect(screen.getByText(/PAT000100.*1990-03-14/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Different person' }))
    await waitFor(() => expect(screen.queryByText(/patient to check/)).not.toBeInTheDocument())
  })

  it('shows nothing when there is no one to check or the role cannot see patients', async () => {
    const empty = mockApi({ 'GET /patients/to-review': () => [] })
    const { container, unmount } = render(<PatientReviewCard />)
    await Promise.resolve()
    await waitFor(() => expect(empty).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
    unmount()
    const refused = mockApi({ 'GET /patients/to-review': () => reply(403, { detail: 'No' }) })
    const denied = render(<PatientReviewCard />)
    await waitFor(() => expect(refused).toHaveBeenCalled())
    expect(denied.container).toBeEmptyDOMElement()
  })
})
