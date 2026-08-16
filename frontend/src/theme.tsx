import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { useColorScheme } from "react-native";

import { fonts } from "@/src/hooks/use-app-fonts";
import { storage } from "@/src/utils/storage";

export const light = {
  bg: "#F7F5F1", surface: "#FFFFFF", alt: "#EFEDE6", ink: "#1C1922", muted: "#6B6772",
  faint: "#9B96A2", primary: "#5138C9", onPrimary: "#FFFFFF", primarySoft: "#ECE8FB",
  green: "#1E8E5A", greenSoft: "#E2F2E9", danger: "#C2453B", dangerSoft: "#F9E9E7",
  amber: "#B07B18", border: "#E6E3DB", scrim: "rgba(24,20,30,0.45)",
  accent: "#FF6A39", onAccent: "#1C1922", accentSoft: "#FFE4D9",
};
export const dark: typeof light = {
  bg: "#131118", surface: "#1C1923", alt: "#262230", ink: "#F5F2EC", muted: "#ABA5B4",
  faint: "#7B7684", primary: "#A395F2", onPrimary: "#191430", primarySoft: "#2A2442",
  green: "#5FCE96", greenSoft: "#1E3129", danger: "#E1766D", dangerSoft: "#3A2523",
  amber: "#E0B45E", border: "#332E3E", scrim: "rgba(0,0,0,0.55)",
  accent: "#FF8A62", onAccent: "#1C1211", accentSoft: "#3A2620",
};

export type Colors = typeof light;
export type ThemePref = "light" | "dark" | "system";

// Shared scales — theme-independent, so plain exports rather than context values.
// New/redesigned screens should build from these instead of ad hoc numbers.
export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 20, xxl: 24, xxxl: 32 };
export const radius = { sm: 12, md: 16, lg: 20, xl: 24, pill: 999 };
// Manrope for headings (distinct, geometric — the brand voice), IBM Plex Sans for
// everything read at length (body/UI). Weight lives in the font family itself
// (each is a separate static font file), so no fontWeight alongside these.
export const type = {
  display: { fontFamily: fonts.headingExtraBold, fontSize: 28, letterSpacing: -0.6 },
  h1: { fontFamily: fonts.headingExtraBold, fontSize: 23, letterSpacing: -0.5 },
  h2: { fontFamily: fonts.headingBold, fontSize: 18, letterSpacing: -0.3 },
  body: { fontFamily: fonts.bodyMedium, fontSize: 15 },
  bodyStrong: { fontFamily: fonts.bodyBold, fontSize: 15 },
  small: { fontFamily: fonts.bodyMedium, fontSize: 13 },
  micro: { fontFamily: fonts.bodyBold, fontSize: 11, textTransform: "uppercase" as const, letterSpacing: 0.6 },
};

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
