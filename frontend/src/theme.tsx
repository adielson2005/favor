import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { useColorScheme } from "react-native";

import { storage } from "@/src/utils/storage";

export const light = {
  bg: "#F7F5F1", surface: "#FFFFFF", alt: "#EFEDE6", ink: "#1C1922", muted: "#6B6772",
  faint: "#9B96A2", primary: "#5138C9", onPrimary: "#FFFFFF", primarySoft: "#ECE8FB",
  green: "#1E8E5A", greenSoft: "#E2F2E9", danger: "#C2453B", dangerSoft: "#F9E9E7",
  amber: "#B07B18", border: "#E6E3DB", scrim: "rgba(24,20,30,0.45)",
};
export const dark: typeof light = {
  bg: "#131118", surface: "#1C1923", alt: "#262230", ink: "#F5F2EC", muted: "#ABA5B4",
  faint: "#7B7684", primary: "#A395F2", onPrimary: "#191430", primarySoft: "#2A2442",
  green: "#5FCE96", greenSoft: "#1E3129", danger: "#E1766D", dangerSoft: "#3A2523",
  amber: "#E0B45E", border: "#332E3E", scrim: "rgba(0,0,0,0.55)",
};

export type Colors = typeof light;
export type ThemePref = "light" | "dark" | "system";

const ThemeContext = createContext<{ colors: Colors; isDark: boolean; pref: ThemePref; setPref: (p: ThemePref) => void }>({ colors: light, isDark: false, pref: "system", setPref: () => {} });

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const system = useColorScheme();
  const [pref, setPrefState] = useState<ThemePref>("system");

  useEffect(() => {
    storage.getItem("faze:theme", "system").then((v) => setPrefState((v as ThemePref) || "system"));
  }, []);

  const setPref = (p: ThemePref) => {
    setPrefState(p);
    storage.setItem("faze:theme", p);
  };

  const isDark = pref === "system" ? system === "dark" : pref === "dark";
  const value = useMemo(() => ({ colors: isDark ? dark : light, isDark, pref, setPref }), [isDark, pref]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export const useTheme = () => useContext(ThemeContext);
