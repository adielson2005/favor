// Single source of truth for responsive behavior. Reacts live to window resize
// (useWindowDimensions subscribes to the 'change' event), so rotating a device
// or resizing a browser window re-evaluates the breakpoint automatically —
// no manual "detect platform" branching needed anywhere else in the app.
import { useWindowDimensions } from "react-native";

export const BREAKPOINTS = { tablet: 768, desktop: 1024 };

export type Breakpoint = "mobile" | "tablet" | "desktop";

export function useBreakpoint(): { breakpoint: Breakpoint; width: number; isDesktop: boolean; isTablet: boolean; isMobile: boolean } {
  const { width } = useWindowDimensions();
  const breakpoint: Breakpoint = width >= BREAKPOINTS.desktop ? "desktop" : width >= BREAKPOINTS.tablet ? "tablet" : "mobile";
  return {
    breakpoint, width,
    isDesktop: breakpoint === "desktop",
    isTablet: breakpoint === "tablet",
    isMobile: breakpoint === "mobile",
  };
}
