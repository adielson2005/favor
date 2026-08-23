import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { useColorScheme } from "react-native";

import { fonts } from "@/src/hooks/use-app-fonts";
import { storage } from "@/src/utils/storage";

// Palette sampled directly from the fazum brand mark (logo-mark.png): navy #091323,
// gradient green from #0A7335 to the lime #A4ED0E. `primary` uses the deeper green —
// legible with white text on buttons — while `accent` keeps the lime for small
// highlights (the wordmark's dot, badges) where a light color reads fine.
export const light = {
  bg: "#F7F5F1", surface: "#FFFFFF", alt: "#EFEDE6", ink: "#0E1A2B", muted: "#5C6670",
  faint: "#8C949C", primary: "#12864A", onPrimary: "#FFFFFF", primarySoft: "#E1F5E9",
  green: "#1E8E5A", greenSoft: "#E2F2E9", danger: "#C2453B", dangerSoft: "#F9E9E7",
  amber: "#B07B18", border: "#E6E3DB", scrim: "rgba(9,19,35,0.45)",
  accent: "#A4ED0E", onAccent: "#0E1A2B", accentSoft: "#EEFAD1",
};
export const dark: typeof light = {
  bg: "#091323", surface: "#111E33", alt: "#16273F", ink: "#F3F6F4", muted: "#9AA6B2",
  faint: "#6C7A8A", primary: "#34C471", onPrimary: "#04180D", primarySoft: "#123322",
  green: "#5FCE96", greenSoft: "#1E3129", danger: "#E1766D", dangerSoft: "#3A2523",
  amber: "#E0B45E", border: "#22344B", scrim: "rgba(0,0,0,0.55)",
  accent: "#C6F542", onAccent: "#0E1A2B", accentSoft: "#20301A",
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

export const ThemeContext = createContext<{ colors: Colors; isDark: boolean; pref: ThemePref; setPref: (p: ThemePref) => void }>({ colors: light, isDark: false, pref: "system", setPref: () => {} });

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
