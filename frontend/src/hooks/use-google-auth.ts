// Google Sign-In via expo-auth-session. Needs a real OAuth Client ID to work —
// see frontend/.env's EXPO_PUBLIC_GOOGLE_CLIENT_ID (Web application type, from
// Google Cloud Console > APIs & Services > Credentials) and the matching
// GOOGLE_CLIENT_ID in backend/.env (same client, both sides verify against it).
// EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS / _ANDROID are optional platform-specific client
// IDs (iOS/Android OAuth client types) — falls back to the web client ID when unset.
import { useMemo } from "react";
import Constants from "expo-constants";
import * as Crypto from "expo-crypto";
import * as Google from "expo-auth-session/providers/google";
import * as WebBrowser from "expo-web-browser";

WebBrowser.maybeCompleteAuthSession();

const CLIENT_ID = Constants.expoConfig?.extra?.googleClientId || process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID || "";
const IOS_CLIENT_ID = Constants.expoConfig?.extra?.googleClientIdIos || process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS || "";
const ANDROID_CLIENT_ID = Constants.expoConfig?.extra?.googleClientIdAndroid || process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID || "";

export function useGoogleAuth() {
  const configured = !!CLIENT_ID;
  // One nonce per mount of the screen that calls this hook (login/signup remount it on
  // every visit) — sent to the backend alongside the id_token so it can confirm the
  // token was minted for THIS sign-in attempt, not replayed from a captured older one.
  const nonce = useMemo(() => Crypto.randomUUID(), []);
  const [request, response, promptAsync] = Google.useAuthRequest(
    configured
      ? {
          webClientId: CLIENT_ID,
          clientId: CLIENT_ID,
          iosClientId: IOS_CLIENT_ID || undefined,
          androidClientId: ANDROID_CLIENT_ID || undefined,
          extraParams: { nonce },
        }
      : { webClientId: "placeholder" },
  );
  return { configured, ready: !!request, response, promptAsync, nonce };
}

export function extractIdToken(response: ReturnType<typeof Google.useAuthRequest>[1]): string | null {
  if (response?.type !== "success") return null;
  return response.authentication?.idToken || (response.params as Record<string, string> | undefined)?.id_token || null;
}
