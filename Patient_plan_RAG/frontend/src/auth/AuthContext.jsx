import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, AUTH_REQUIRED_EVENT } from "../services/api";

const AuthContext = createContext(null);

/**
 * Holds the signed-in user ({username, role, plan_ids, must_change_password})
 * or null. Asks the server on load; any 401 from the API signs the app out.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.me().then(setUser).catch(() => setUser(null)).finally(() => setLoading(false));
    const onAuthRequired = () => setUser(null);
    window.addEventListener(AUTH_REQUIRED_EVENT, onAuthRequired);
    return () => window.removeEventListener(AUTH_REQUIRED_EVENT, onAuthRequired);
  }, []);

  const signIn = useCallback(async (username, password) => {
    setUser(await api.login(username, password));
  }, []);

  const register = useCallback(async (username, password) => {
    setUser(await api.register(username, password));
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setUser(null);
    }
  }, []);

  const changePassword = useCallback(async (current, next) => {
    setUser(await api.changePassword(current, next));
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, signIn, register, signOut, changePassword }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
