import { Ionicons } from "@expo/vector-icons";
import React from "react";
import { Image, Text, View } from "react-native";

import { fonts } from "@/src/hooks/use-app-fonts";
import { useTheme } from "@/src/theme";

const MARK_ASSET = require("@/assets/images/logo-mark.png");
const MARK_ASPECT = 920 / 950; // logo-mark.png's own width/height

export function LogoMark({ size = 40 }: { size?: number }) {
  return (
    <Image
      source={MARK_ASSET}
      resizeMode="contain"
      style={{ width: size * MARK_ASPECT, height: size }}
    />
  );
}

export function Wordmark({ size = 26 }: { size?: number }) {
  const { colors } = useTheme();
  return (
    <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: size, letterSpacing: -0.5 }}>
      fazum<Text style={{ color: colors.accent }}>.</Text>
    </Text>
  );
}

export function Brand({ size = 40, gap = 10 }: { size?: number; gap?: number }) {
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap }}>
      <LogoMark size={size} />
      <Wordmark size={size * 0.6} />
    </View>
  );
}

// The wallet's sub-brand lockup — same pattern real marketplace apps use for their
// in-app wallet (99Pay, iFood Card, Uber Wallet): a small icon badge + wordmark
// distinct from the main brand mark. `light` renders it for use on a dark/gradient
// background (the balance card); otherwise it uses the current theme's ink color.
export function FazumPayMark({ size = 22, light = false }: { size?: number; light?: boolean }) {
  const { colors } = useTheme();
  const fg = light ? "#FFFFFF" : colors.ink;
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: size * 0.34 }}>
      <View style={{
        width: size, height: size, borderRadius: size / 2,
        backgroundColor: light ? "rgba(255,255,255,0.18)" : colors.primarySoft,
        alignItems: "center", justifyContent: "center",
      }}>
        <Ionicons name="wallet" size={size * 0.56} color={light ? "#FFFFFF" : colors.primary} />
      </View>
      <Text style={{ color: fg, fontFamily: fonts.headingExtraBold, fontSize: size * 0.66, letterSpacing: -0.3 }}>
        fazum<Text style={{ color: colors.accent }}>Pay</Text>
      </Text>
    </View>
  );
}
