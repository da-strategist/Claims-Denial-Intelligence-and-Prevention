import { vi } from 'vitest'

const REPLY = Symbol('reply')

/** A response with a status other than 200. */
export const reply = (status, body) => ({ [REPLY]: true, status, body })

/** "POST /claims" for a fetch call (the /api prefix and query string dropped). */
function routeKey(url, init = {}) {
  const { pathname } = new URL(url, 'http://localhost')
  return `${init.method ?? 'GET'} ${pathname.replace(/^\/api/, '')}`
}

/**
 * Stub fetch with handlers keyed by route ("GET /patients"). A handler receives
 * { params, body } and returns the JSON body, or `reply(status, body)`.
 * Returns the mock so tests can inspect the calls.
 */
export function mockApi(handlers) {
  const fetchMock = vi.fn(async (url, init = {}) => {
    const key = routeKey(url, init)
    const handler = handlers[key]
    if (!handler) throw new Error(`No mock for ${key}`)
    const result = await handler({
      params: Object.fromEntries(new URL(url, 'http://localhost').searchParams),
      body: init.body ? JSON.parse(init.body) : undefined,
    })
    const { status = 200, body } = result?.[REPLY] ? result : { body: result }
    return new Response(status === 204 ? null : JSON.stringify(body), {
      status,
      statusText: status >= 400 ? 'Error' : 'OK',
      headers: { 'Content-Type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** JSON bodies the app sent to a route. */
export const sentBodies = (fetchMock, key) =>
  fetchMock.mock.calls
    .filter(([url, init]) => routeKey(url, init) === key)
    .map(([, init]) => JSON.parse(init.body))
