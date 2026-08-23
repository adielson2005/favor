import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, Category, City, Neighborhood, User } from "@/src/api";
import { useAuth } from "@/src/auth";
import { storage } from "@/src/utils/storage";

// "mode" is a pure view toggle — it changes which orders Home/Explore surface for the
// single logged-in account, it never changes who the account is (see src/auth.tsx).
type Mode = "client" | "worker";

type AppState = {
  loading: boolean;
  error: boolean;
  retry: () => void;
  me: User;
  mode: Mode;
  setMode: (m: Mode) => void;
  categories: Category[];
  cities: City[];
  neighborhoods: Neighborhood[];
  city: City | null;
  unread: number;
  refreshUnread: () => void;
  refreshMe: () => void;
  featureFlags: Record<string, boolean>;
};

const AppContext = createContext<AppState>(null as never);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const { user, refreshUser } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [mode, setModeState] = useState<Mode>("client");
  const [categories, setCategories] = useState<Category[]>([]);
  const [cities, setCities] = useState<City[]>([]);
  const [neighborhoods, setNeighborhoods] = useState<Neighborhood[]>([]);
  const [unread, setUnread] = useState(0);
  const [featureFlags, setFeatureFlags] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const data = await api.get("/bootstrap");
      setCategories(data.categories || []);
      setCities(data.cities || []);
      setNeighborhoods(data.neighborhoods || []);
      setFeatureFlags(data.feature_flags || {});
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    storage.getItem("faze:mode", "client").then((v) => setModeState((v as Mode) || "client"));
    load();
  }, [load]);

  const setMode = (m: Mode) => {
    setModeState(m);
    storage.setItem("faze:mode", m);
  };

  const refreshUnread = useCallback(() => {
    if (!user) return;
    api.get("/notifications").then((d) => setUnread(d.unread || 0)).catch(() => {});
  }, [user]);

  useEffect(() => { refreshUnread(); }, [refreshUnread]);

  const city = cities.find((c) => c.id === user?.city_id) || cities[0] || null;

  const value = useMemo(
    () => ({ loading, error, retry: load, me: user as User, mode, setMode, categories, cities, neighborhoods, city, unread, refreshUnread, refreshMe: refreshUser, featureFlags }),
    [loading, error, load, user, mode, categories, cities, neighborhoods, city, unread, refreshUnread, refreshUser, featureFlags],
  );
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export const useApp = () => useContext(AppContext);
