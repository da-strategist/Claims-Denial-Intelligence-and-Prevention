import { describe, expect, it, vi } from 'vitest'
import { mockApi, reply } from '../test/mockApi'
import { createClaim, deleteRule, listClaims } from './api'

describe('API client', () => {
  it('drops empty query parameters', async () => {
    const fetchMock = mockApi({ 'GET /claims': () => ({ items: [] }) })
    await listClaims({ search: 'CLM1', status: '', payer_id: null, page: 2 })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/claims?search=CLM1&page=2')
  })

  it('turns FastAPI validation errors into one readable message', async () => {
    mockApi({
      'POST /claims': () =>
        reply(422, {
          detail: [
            { loc: ['body', 'lines', 0, 'units'], msg: 'Input should be greater than 0' },
            { loc: ['body'], msg: 'Value error, Each payer can only be listed once' },
          ],
        }),
    })
    await expect(createClaim({})).rejects.toThrow(
      'lines › 0 › units: Input should be greater than 0; Each payer can only be listed once',
    )
  })

  it('passes string errors through and falls back to the status', async () => {
    mockApi({ 'GET /claims': () => reply(404, { detail: 'Claim CLM9 not found' }) })
    await expect(listClaims()).rejects.toThrow('Claim CLM9 not found')
    mockApi({ 'GET /claims': () => reply(500, 'oops') })
    await expect(listClaims()).rejects.toThrow('Request failed: 500 Error')
  })

  it('says when the API server can’t be reached', async () => {
    mockApi({ 'GET /claims': () => reply(502, '') })
    await expect(listClaims()).rejects.toThrow('Can’t reach the API server')
    vi.stubGlobal('fetch', () => Promise.reject(new TypeError('Failed to fetch')))
    await expect(listClaims()).rejects.toThrow('Can’t reach the API server')
  })

  it('lets aborted requests through as aborts', async () => {
    vi.stubGlobal('fetch', () => Promise.reject(new DOMException('Aborted', 'AbortError')))
    await expect(listClaims()).rejects.toHaveProperty('name', 'AbortError')
  })

  it('returns null for 204 No Content', async () => {
    mockApi({ 'DELETE /rules/RULE-001': () => reply(204) })
    await expect(deleteRule('RULE-001')).resolves.toBeNull()
  })
})
