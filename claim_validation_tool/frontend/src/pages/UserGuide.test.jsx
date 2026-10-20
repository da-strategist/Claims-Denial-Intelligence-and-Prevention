import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AuthContext } from '../hooks/useAuth'
import UserGuide from './UserGuide'

const user = (role, permissions) => ({ user: { role, permissions, idle_timeout_minutes: 15 } })
const headings = () => screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)

function renderAs(auth) {
  render(
    <AuthContext.Provider value={auth}>
      <UserGuide />
    </AuthContext.Provider>,
  )
}

describe('UserGuide', () => {
  it('shows analysts only what they can do', () => {
    renderAs(user('analyst', ['claims:read']))
    expect(headings()).toEqual([
      'Getting started',
      'Overview',
      'Fixing claims that need attention',
      'What the labels mean',
    ])
    expect(screen.getByText(/applying them needs a biller/)).toBeInTheDocument()
    expect(screen.getByText(/after 15 minutes without activity/i)).toBeInTheDocument()
  })

  it('adds claim entry and drafts for billers, and the admin section for administrators', () => {
    renderAs(user('biller', ['claims:read', 'claims:write', 'patients:read']))
    expect(headings()).toContain('Drafts: picking up unfinished work')
    expect(headings()).toContain('Why won’t my claim submit?')
    expect(headings()).not.toContain('For administrators')
  })

  it('shows administrators everything', () => {
    renderAs(user('admin', ['audit:read', 'claims:read', 'claims:write', 'patients:read', 'rules:write']))
    expect(headings()).toHaveLength(8)
    expect(headings().at(-1)).toBe('For administrators')
  })
})
