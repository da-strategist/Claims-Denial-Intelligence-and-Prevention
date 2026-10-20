import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ErrorBoundary from './ErrorBoundary'

function Broken() {
  throw new Error('Cannot read properties of undefined')
}

describe('ErrorBoundary', () => {
  it('replaces a crashed page with a message and a reload button', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <ErrorBoundary>
        <Broken />
      </ErrorBoundary>,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Something went wrong on this page')
    expect(screen.getByText('Cannot read properties of undefined')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reload page' })).toBeInTheDocument()
  })

  it('renders its children when nothing fails', () => {
    render(<ErrorBoundary>Claims</ErrorBoundary>)
    expect(screen.getByText('Claims')).toBeInTheDocument()
  })
})
