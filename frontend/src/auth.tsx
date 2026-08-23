import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, markAuthReady, setAuthToken, User } from "@/src/api";
import { storage } from "@/src/utils/storage";

const TOKEN_KEY = "faze:token";

type AuthState = {
  ready: boolean;
  token: string | null;
  user: User | null;
  login: (identifier: string, password: string) => Promise<void>;
  register: (data: { name: string; email: string; phone: string; password: string; city_id: string; neighborhood_id?: string | null; preference?: "client" | "worker" | "both"; accept_terms: boolean }) => Promise<void>;
  loginWithGoogle: (idToken: string, nonce?: string, cityId?: string) => Promise<User>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  deleteAccount: () => Promise<void>;
  // For endpoints other than login/register that also issue a fresh session (e.g.
  // change-email/change-phone, which invalidate the caller's own token as a side
  // effect of the account change) — lets the caller carry on with the new token
  // instead of being forced to log in again mid-flow.
  syncSession: (token: string, user: User) => Promise<void>;
};

const AuthContext = createContext<AuthState>(null as never);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);

  const applySession = useCallback((nextToken: string, nextUser: User) => {
    setAuthToken(nextToken);
    setToken(nextToken);
    setUser(nextUser);
  }, []);

  useEffect(() => {
    (async () => {
      const stored = await storage.secureGet(TOKEN_KEY, "");
      if (stored) setAuthToken(stored);
      // authToken is now settled to its stored value (or null) — safe to unblock every
      // other request() caller. Must happen BEFORE the /auth/me verification call below,
      // since that call itself goes through request(), which awaits this same promise.
      markAuthReady();
      if (stored) {
        try {
          const me = await api.get("/auth/me");
          setToken(stored);
          setUser(me);
        } catch {
          await storage.secureRemove(TOKEN_KEY);
          setAuthToken(null);
        }
      }
      setReady(true);
    })();
  }, []);

  const login = useCallback(async (identifier: string, password: string) => {
    const data = await api.post("/auth/login", { identifier: identifier.trim(), password });
    await storage.secureSet(TOKEN_KEY, data.token);
    applySession(data.token, data.user);
  }, [applySession]);

  const register = useCallback(async (payload: { name: string; email: string; phone: string; password: string; city_id: string; neighborhood_id?: string | null; preference?: "client" | "worker" | "both"; accept_terms: boolean }) => {
    const data = await api.post("/auth/register", payload);
    await storage.secureSet(TOKEN_KEY, data.token);
    applySession(data.token, data.user);
  }, [applySession]);

  const loginWithGoogle = useCallback(async (idToken: string, nonce?: string, cityId?: string) => {
    const data = await api.post("/auth/google", { id_token: idToken, nonce, city_id: cityId || "city-parauapebas" });
    await storage.secureSet(TOKEN_KEY, data.token);
    applySession(data.token, data.user);
    return data.user as User;
  }, [applySession]);

  const changePassword = useCallback(async (currentPassword: string, newPassword: string) => {
    await api.post("/auth/change-password", { current_password: currentPassword, new_password: newPassword });
  }, []);

  const syncSession = useCallback(async (nextToken: string, nextUser: User) => {
    await storage.secureSet(TOKEN_KEY, nextToken);
    applySession(nextToken, nextUser);
  }, [applySession]);

  const deleteAccount = useCallback(async () => {
    await api.del("/auth/me");
    await storage.secureRemove(TOKEN_KEY);
    setAuthToken(null);
    setToken(null);
    setUser(null);
  }, []);

  const logout = useCallback(async () => {
    await storage.secureRemove(TOKEN_KEY);
    setAuthToken(null);
    setToken(null);
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const me = await api.get("/auth/me");
      setUser(me);
    } catch { /* keep last known user */ }
  }, []);

  const value = useMemo(() => ({ ready, token, user, login, register, loginWithGoogle, logout, refreshUser, changePassword, deleteAccount, syncSession }),
    [ready, token, user, login, register, loginWithGoogle, logout, refreshUser, changePassword, deleteAccount, syncSession]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
