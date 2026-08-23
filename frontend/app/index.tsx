import { useRouter } from "expo-router";
import { useEffect } from "react";
import { ActivityIndicator, View } from "react-native";

import { useAuth } from "@/src/auth";
import { Brand } from "@/src/components/Logo";
import { useTheme } from "@/src/theme";
import { storage } from "@/src/utils/storage";

export default function Gate() {
  const router = useRouter();
  const { colors } = useTheme();
  const { ready, token, user } = useAuth();

  useEffect(() => {
    if (!ready) return;
    if (!token) {
      router.replace("/auth/welcome");
      return;
    }
    // Safety net for anyone who left mid Google sign-up before finishing the
    // complete-profile phone step (e.g. closed the app) — login/signup already
    // redirect there right after a fresh Google sign-in.
    if (user && !user.phone) {
      router.replace("/auth/complete-profile");
      return;
    }
    storage.getItem("faze:onboarded", false).then((seen) => {
      router.replace(seen ? "/(tabs)/home" : "/onboarding");
    });
  }, [ready, token, user, router]);

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", gap: 20 }}>
      <Brand size={56} />
      <ActivityIndicator color={colors.primary} />
    </View>
  );
}
