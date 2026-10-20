import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { getMe, login, logout, SIGNED_OUT_EVENT } from '../services/api'

/**
 * The signed-in user: { user, status, notice, signIn, signOut }. `status` is 'loading',
 * 'signed-out', or 'signed-in'. The API enforces every permission; the UI only uses them
 * to hide what a role can't do.
 */
export const AuthContext = createContext(null)

export const useAuth = () => useContext(AuthContext)

/** Whether the signed-in user's role has `permission` (e.g. 'claims:write'). */
export function useCan(permission) {
  return useContext(AuthContext)?.user?.permissions.includes(permission) ?? false
}

/** State for AuthContext.Provider: checks the session cookie, and signs out on any 401. */
export function useAuthState() {
  const [state, setState] = useState({ status: 'loading', user: null, notice: null })

  useEffect(() => {
    getMe()
      .then((user) => setState({ status: 'signed-in', user, notice: null }))
      .catch(() => setState({ status: 'signed-out', user: null, notice: null }))
  }, [])

  // The session ended on the server (idle timeout, sign-out elsewhere, account disabled)
  useEffect(() => {
    const onSignedOut = () =>
      setState((prev) =>
        prev.status === 'signed-in'
          ? { status: 'signed-out', user: null, notice: 'Your session ended. Sign in again to continue.' }
          : prev,
      )
    window.addEventListener(SIGNED_OUT_EVENT, onSignedOut)
    return () => window.removeEventListener(SIGNED_OUT_EVENT, onSignedOut)
  }, [])

  const signIn = useCallback(async (username, password) => {
    const user = await login(username, password)
    setState({ status: 'signed-in', user, notice: null })
  }, [])

  const signOut = useCallback(async () => {
    try {
      await logout()
    } finally {
      setState({ status: 'signed-out', user: null, notice: 'You signed out.' })
    }
  }, [])

  // Re-read who is signed in (e.g. after a platform account starts or ends emergency access)
  const refresh = useCallback(async () => {
    const user = await getMe()
    setState({ status: 'signed-in', user, notice: null })
    return user
  }, [])

  return { ...state, signIn, signOut, refresh }
}
