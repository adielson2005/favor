// Google Sign-In via expo-auth-session. Needs a real OAuth Client ID to work —
// see frontend/.env's EXPO_PUBLIC_GOOGLE_CLIENT_ID (Web application type, from
// Google Cloud Console > APIs & Services > Credentials) and the matching
// GOOGLE_CLIENT_ID in backend/.env (same client, both sides verify against it).
import Constants from "expo-constants";
import * as Google from "expo-auth-session/providers/google";
import * as WebBrowser from "expo-web-browser";

WebBrowser.maybeCompleteAuthSession();

const CLIENT_ID = Constants.expoConfig?.extra?.googleClientId || process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID || "";

export function useGoogleAuth() {
  const configured = !!CLIENT_ID;
  const [request, response, promptAsync] = Google.useAuthRequest(
    configured ? { webClientId: CLIENT_ID, clientId: CLIENT_ID } : { webClientId: "placeholder" },
  );
  return { configured, ready: !!request, response, promptAsync };
}

export function extractIdToken(response: ReturnType<typeof Google.useAuthRequest>[1]): string | null {
  if (response?.type !== "success") return null;
  return response.authentication?.idToken || (response.params as Record<string, string> | undefined)?.id_token || null;
}
