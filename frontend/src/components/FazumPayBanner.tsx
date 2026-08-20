import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import React from "react";
import { Text, View } from "react-native";

import { fonts } from "@/src/hooks/use-app-fonts";
import { radius, useTheme } from "@/src/theme";

type Icon = keyof typeof Ionicons.glyphMap;

const FEATURES: { icon: Icon; label: string }[] = [
  { icon: "wallet-outline", label: "Guarde e receba" },
  { icon: "shield-checkmark-outline", label: "Segurança" },
  { icon: "flash-outline", label: "100% digital" },
];

// Home-screen promo for the wallet — same gradient/texture language as the
// wallet's own balance card (src/components/Logo.tsx's FazumPayMark, app/wallet/index.tsx),
// so the banner reads as "this app has a wallet called fazumPay" rather than a
// generic ad. The mini balance card on the right echoes the real wallet screen
// (masked amount, eye icon) so tapping through feels like a preview, not a surprise.
// Sized to fill whatever box HighlightsCarousel gives it.
export function FazumPayBanner() {
  const { colors } = useTheme();
  return (
    <LinearGradient
      colors={["#091323", "#0A7335"]}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={{ flex: 1, borderRadius: radius.lg, overflow: "hidden" }}
    >
      <View pointerEvents="none" style={{ position: "absolute", top: "-35%", right: "-10%", width: "55%", aspectRatio: 1, borderRadius: 999, backgroundColor: "rgba(255,255,255,0.06)" }} />
      <View pointerEvents="none" style={{ position: "absolute", bottom: "-40%", left: "20%", width: "45%", aspectRatio: 1, borderRadius: 999, backgroundColor: "rgba(164,237,14,0.06)" }} />

      <View style={{ flex: 1, flexDirection: "row", alignItems: "center", paddingHorizontal: "6%", gap: "4%" }}>
        <View style={{ flex: 1, gap: 5 }}>
          <View style={{ flexDirection: "row", alignSelf: "flex-start", borderWidth: 1, borderColor: "rgba(164,237,14,0.5)", borderRadius: radius.pill, paddingHorizontal: 10, paddingVertical: 3 }}>
            <Text style={{ color: colors.accent, fontFamily: fonts.bodyBold, fontSize: 10, textTransform: "uppercase", letterSpacing: 1 }}>Chegou a</Text>
          </View>
          <Text style={{ color: "#FFFFFF", fontFamily: fonts.headingExtraBold, fontSize: 30, letterSpacing: -1, lineHeight: 32 }}>
            fazum<Text style={{ color: colors.accent }}>Pay</Text>
          </Text>
          <Text style={{ color: "rgba(255,255,255,0.75)", fontFamily: fonts.bodyMedium, fontSize: 12, lineHeight: 16, maxWidth: 260 }} numberOfLines={2}>
            A carteira digital da fazum para guardar, receber e sacar o que você ganha.
          </Text>

          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 14, marginTop: 6 }}>
            {FEATURES.map((f) => (
              <View key={f.label} style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
                <Ionicons name={f.icon} size={12} color={colors.accent} />
                <Text style={{ color: "rgba(255,255,255,0.85)", fontFamily: fonts.bodySemiBold, fontSize: 10 }}>{f.label}</Text>
              </View>
            ))}
          </View>
        </View>

        <View style={{ width: 92, borderRadius: radius.md, backgroundColor: "rgba(255,255,255,0.1)", borderWidth: 1, borderColor: "rgba(255,255,255,0.16)", padding: 10, gap: 6 }}>
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
            <Text style={{ color: "rgba(255,255,255,0.6)", fontFamily: fonts.bodyBold, fontSize: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>Saldo</Text>
            <Ionicons name="eye-off-outline" size={10} color="rgba(255,255,255,0.6)" />
          </View>
          <Text style={{ color: "#FFFFFF", fontFamily: fonts.headingExtraBold, fontSize: 15, letterSpacing: -0.3 }}>R$ ••••</Text>
          <View style={{ height: 1, backgroundColor: "rgba(255,255,255,0.14)" }} />
          <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
            <Text style={{ color: colors.accent, fontFamily: fonts.bodySemiBold, fontSize: 9 }}>Abrir</Text>
            <Ionicons name="arrow-forward" size={10} color={colors.accent} />
          </View>
        </View>
      </View>
    </LinearGradient>
  );
}
