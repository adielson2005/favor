import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, markAuthReady, setAuthToken, User } from "@/src/api";
import { storage } from "@/src/utils/storage";

const TOKEN_KEY = "faze:token";

type AuthState = {
  ready: boolean;
  token: string | null;
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { name: string; email: string; password: string; city_id: string; neighborhood_id?: string | null; preference?: "client" | "worker" | "both" }) => Promise<void>;
  loginWithGoogle: (idToken: string, cityId?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  deleteAccount: () => Promise<void>;
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

  const login = useCallback(async (email: string, password: string) => {
    const data = await api.post("/auth/login", { email: email.trim().toLowerCase(), password });
    await storage.secureSet(TOKEN_KEY, data.token);
    applySession(data.token, data.user);
  }, [applySession]);

  const register = useCallback(async (payload: { name: string; email: string; password: string; city_id: string; neighborhood_id?: string | null; preference?: "client" | "worker" | "both" }) => {
    const data = await api.post("/auth/register", payload);
    await storage.secureSet(TOKEN_KEY, data.token);
    applySession(data.token, data.user);
  }, [applySession]);

  const loginWithGoogle = useCallback(async (idToken: string, cityId?: string) => {
    const data = await api.post("/auth/google", { id_token: idToken, city_id: cityId || "city-parauapebas" });
    await storage.secureSet(TOKEN_KEY, data.token);
    applySession(data.token, data.user);
  }, [applySession]);

  const changePassword = useCallback(async (currentPassword: string, newPassword: string) => {
    await api.post("/auth/change-password", { current_password: currentPassword, new_password: newPassword });
  }, []);

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

  const value = useMemo(() => ({ ready, token, user, login, register, loginWithGoogle, logout, refreshUser, changePassword, deleteAccount }),
    [ready, token, user, login, register, loginWithGoogle, logout, refreshUser, changePassword, deleteAccount]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
