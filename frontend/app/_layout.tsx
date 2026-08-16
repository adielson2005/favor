import { Stack, usePathname } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { useEffect, useLayoutEffect } from "react";
import { LogBox, Platform } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";

import { AuthProvider } from "@/src/auth";
import { ErrorBoundary } from "@/src/components/ErrorBoundary";
import { useAppFonts } from "@/src/hooks/use-app-fonts";
import { useIconFonts } from "@/src/hooks/use-icon-fonts";
import { AppProvider } from "@/src/state";
import { ThemeProvider, useTheme } from "@/src/theme";


// Disable logbox errors etc so that users can see the app
// and agent works as expected.
LogBox.ignoreAllLogs(true)

// Keep the native splash visible from cold start until icon fonts register.
// Required because @expo/vector-icons' componentDidMount fallback fires
// Font.loadAsync against a broken vendor path if any <Icon> mounts before
// the family is registered — which throws on Android Expo Go.
SplashScreen.preventAutoHideAsync();

function AppStack() {
  const { isDark, colors } = useTheme();
  const pathname = usePathname();

  // Web-only: when navigating away, expo-router marks the outgoing screen aria-hidden
  // before the browser has cleared focus from whatever input/button was focused inside
  // it, which trips a console warning ("aria-hidden blocked... descendant retained
  // focus"). Blurring on every route change — before paint — clears focus early enough
  // to avoid it. No-op on native, where this DOM API doesn't exist.
  useLayoutEffect(() => {
    if (Platform.OS !== "web") return;
    (document.activeElement as HTMLElement | null)?.blur?.();
  }, [pathname]);

  return (
    <>
      <StatusBar style={isDark ? "light" : "dark"} />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.bg } }}>
        <Stack.Screen name="create" options={{ presentation: "modal", animation: "slide_from_bottom" }} />
        <Stack.Screen name="auth/welcome" options={{ animation: "fade" }} />
        <Stack.Screen name="auth/login" options={{ animation: "fade" }} />
        <Stack.Screen name="auth/signup" options={{ animation: "slide_from_right" }} />
        <Stack.Screen name="auth/forgot-password" options={{ animation: "slide_from_right" }} />
        <Stack.Screen name="auth/verify-email" options={{ animation: "slide_from_right" }} />
      </Stack>
    </>
  );
}

export default function RootLayout() {
  const [iconsLoaded, iconsError] = useIconFonts();
  const [typeLoaded, typeError] = useAppFonts();

  useEffect(() => {
    if ((iconsLoaded || iconsError) && (typeLoaded || typeError)) {
      SplashScreen.hideAsync();
    }
  }, [iconsLoaded, iconsError, typeLoaded, typeError]);

  // If a font source is unreachable we fall through on error rather than wedging
  // the app — that family renders with the system fallback, but the app still boots.
  if (!(iconsLoaded || iconsError) || !(typeLoaded || typeError)) return null;

  return (
    <SafeAreaProvider>
      <ThemeProvider>
        <AuthProvider>
          <AppProvider>
            <ErrorBoundary>
              <AppStack />
            </ErrorBoundary>
          </AppProvider>
        </AuthProvider>
      </ThemeProvider>
    </SafeAreaProvider>
  );
}
