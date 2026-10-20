import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useApi } from './useApi'

describe('useApi', () => {
  it('tracks loading, then data', async () => {
    const { result } = renderHook(() => useApi(() => Promise.resolve({ total: 3 })))
    expect(result.current.loading).toBe(true)
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current).toMatchObject({ data: { total: 3 }, error: null })
  })

  it('keeps the previous data when a reload fails', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({ total: 3 })
      .mockRejectedValueOnce(new Error('Server unavailable'))
    const { result } = renderHook(() => useApi(fetcher))
    await waitFor(() => expect(result.current.data).toEqual({ total: 3 }))
    act(() => result.current.reload())
    await waitFor(() => expect(result.current.error).toBe('Server unavailable'))
    expect(result.current.data).toEqual({ total: 3 })
  })

  it('aborts the stale request when the key changes', async () => {
    const signals = []
    const fetcher = (key) => (options) => {
      signals.push(options.signal)
      return Promise.resolve(key)
    }
    const { result, rerender } = renderHook(({ key }) => useApi(fetcher(key), key), {
      initialProps: { key: 'a' },
    })
    rerender({ key: 'b' })
    await waitFor(() => expect(result.current.data).toBe('b'))
    expect(signals.map((s) => s.aborted)).toEqual([true, false])
  })
})
