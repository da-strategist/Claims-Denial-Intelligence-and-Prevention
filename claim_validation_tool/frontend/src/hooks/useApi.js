import { useCallback, useEffect, useState } from 'react'

/**
 * Runs an API call and tracks { data, loading, error }, plus `reload()` to re-run it
 * (e.g. after saving a change). Re-runs when `key` changes (pass a string, e.g. JSON
 * of the request params); stale in-flight requests are aborted. Previous data is
 * kept while reloading so tables don't flash empty.
 */
export function useApi(fetcher, key = '') {
  const [state, setState] = useState({ data: null, loading: true, error: null })
  const [reloads, setReloads] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setState((prev) => ({ ...prev, loading: true, error: null }))

    fetcher({ signal: controller.signal })
      .then((data) => setState({ data, loading: false, error: null }))
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setState((prev) => ({ ...prev, loading: false, error: err.message }))
        }
      })

    return () => controller.abort()
    // `fetcher` is recreated every render; `key` captures what it depends on.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, reloads])

  const reload = useCallback(() => setReloads((n) => n + 1), [])
  return { ...state, reload }
}
