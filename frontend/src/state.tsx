import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, Category, City, Neighborhood, User } from "@/src/api";
import { storage } from "@/src/utils/storage";

type Mode = "client" | "worker";

type AppState = {
  loading: boolean;
  error: boolean;
  retry: () => void;
  users: User[];
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
};

const FALLBACK_ME: User = { id: "demo-client", name: "Você", initials: "VC", rating: 5, rating_count: 0, jobs_done: 0, verified_identity: false, verified_email: false, verified_phone: false, level: "Novo" };

const AppContext = createContext<AppState>(null as never);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [mode, setModeState] = useState<Mode>("client");
  const [categories, setCategories] = useState<Category[]>([]);
  const [cities, setCities] = useState<City[]>([]);
  const [neighborhoods, setNeighborhoods] = useState<Neighborhood[]>([]);
  const [unread, setUnread] = useState(0);

  const meId = mode === "client" ? "demo-client" : "demo-worker";
  const me = users.find((u) => u.id === meId) || FALLBACK_ME;

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const data = await api.get("/bootstrap");
      setUsers(data.users || []);
      setCategories(data.categories || []);
      setCities(data.cities || []);
      setNeighborhoods(data.neighborhoods || []);
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
    api.get(`/notifications?user_id=${meId}`).then((d) => setUnread(d.unread || 0)).catch(() => {});
  }, [meId]);

  const refreshMe = useCallback(() => {
    api.get("/bootstrap").then((d) => setUsers(d.users || [])).catch(() => {});
  }, []);

  useEffect(() => { refreshUnread(); }, [refreshUnread]);

  const city = cities.find((c) => c.id === "city-parauapebas") || cities[0] || null;

  const value = useMemo(
    () => ({ loading, error, retry: load, users, me, mode, setMode, categories, cities, neighborhoods, city, unread, refreshUnread, refreshMe }),
    [loading, error, load, users, me, mode, categories, cities, neighborhoods, city, unread, refreshUnread, refreshMe],
  );
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export const useApp = () => useContext(AppContext);
