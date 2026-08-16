import { useRouter } from "expo-router";
import { useEffect } from "react";
import { ActivityIndicator, Text, View } from "react-native";

import { useTheme } from "@/src/theme";
import { storage } from "@/src/utils/storage";

export default function Gate() {
  const router = useRouter();
  const { colors } = useTheme();

  useEffect(() => {
    storage.getItem("faze:onboarded", false).then((seen) => {
      router.replace(seen ? "/(tabs)/home" : "/onboarding");
    });
  }, [router]);

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", gap: 16 }}>
      <Text style={{ fontSize: 36, fontWeight: "800", color: colors.primary, letterSpacing: -2 }}>FAZÊ</Text>
      <ActivityIndicator color={colors.primary} />
    </View>
  );
}
