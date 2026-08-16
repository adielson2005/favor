import { useRouter } from "expo-router";
import { useEffect } from "react";

import { useAuth } from "@/src/auth";

// Protects a screen reached via deep link / page refresh with no session — without
// this, screens that render `if (!me) return null` just show a blank screen forever
// instead of sending the user to log in.
export function useRequireAuth() {
  const { ready, token } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (ready && !token) router.replace("/auth/welcome");
  }, [ready, token, router]);
}
