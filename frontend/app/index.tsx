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
  const { ready, token } = useAuth();

  useEffect(() => {
    if (!ready) return;
    if (!token) {
      router.replace("/auth/welcome");
      return;
    }
    storage.getItem("faze:onboarded", false).then((seen) => {
      router.replace(seen ? "/(tabs)/home" : "/onboarding");
    });
  }, [ready, token, router]);

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", gap: 20 }}>
      <Brand size={56} />
      <ActivityIndicator color={colors.primary} />
    </View>
  );
}
