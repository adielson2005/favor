import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { AdminMe, adminApi, setAdminToken } from "@/src/admin-api";
import { storage } from "@/src/utils/storage";

const ADMIN_TOKEN_KEY = "faze:admin_token";

type AdminAuthState = {
  ready: boolean;
  token: string | null;
  admin: AdminMe | null;
  login: (email: string, password: string, totpCode?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAdmin: () => Promise<void>;
};

const AdminAuthContext = createContext<AdminAuthState>(null as never);

export function AdminAuthProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [admin, setAdmin] = useState<AdminMe | null>(null);

  const applySession = useCallback((nextToken: string, nextAdmin: AdminMe) => {
    setAdminToken(nextToken);
    setToken(nextToken);
    setAdmin(nextAdmin);
  }, []);

  useEffect(() => {
    (async () => {
      const stored = await storage.secureGet(ADMIN_TOKEN_KEY, "");
      if (stored) {
        setAdminToken(stored);
        try {
          const me = await adminApi.get("/admin/auth/me");
          setToken(stored);
          setAdmin(me);
        } catch {
          await storage.secureRemove(ADMIN_TOKEN_KEY);
          setAdminToken(null);
        }
      }
      setReady(true);
    })();
  }, []);

  const login = useCallback(async (email: string, password: string, totpCode?: string) => {
    const data = await adminApi.post("/admin/auth/login", { email: email.trim().toLowerCase(), password, totp_code: totpCode || undefined });
    await storage.secureSet(ADMIN_TOKEN_KEY, data.token);
    applySession(data.token, data.admin);
  }, [applySession]);

  const logout = useCallback(async () => {
    try { await adminApi.post("/admin/auth/logout"); } catch { /* best-effort */ }
    await storage.secureRemove(ADMIN_TOKEN_KEY);
    setAdminToken(null);
    setToken(null);
    setAdmin(null);
  }, []);

  const refreshAdmin = useCallback(async () => {
    try {
      const me = await adminApi.get("/admin/auth/me");
      setAdmin(me);
    } catch { /* keep last known */ }
  }, []);

  const value = useMemo(() => ({ ready, token, admin, login, logout, refreshAdmin }),
    [ready, token, admin, login, logout, refreshAdmin]);
  return <AdminAuthContext.Provider value={value}>{children}</AdminAuthContext.Provider>;
}

export const useAdminAuth = () => useContext(AdminAuthContext);
