import React from "react";
import { Text, View } from "react-native";

import { fonts } from "@/src/hooks/use-app-fonts";
import { useTheme } from "@/src/theme";

// A custom mark, not an icon-font glyph or emoji: a tilted square with a notch,
// reading as an abstract "task done" check. Built from plain Views so it needs
// no SVG dependency and stays crisp at any size.
export function LogoMark({ size = 40 }: { size?: number }) {
  const { colors } = useTheme();
  const notch = size * 0.34;
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <View style={{
        width: size * 0.78, height: size * 0.78, borderRadius: size * 0.22,
        backgroundColor: colors.primary, transform: [{ rotate: "45deg" }],
      }} />
      <View style={{
        position: "absolute", width: notch, height: notch, borderRadius: notch * 0.3,
        backgroundColor: colors.accent, top: size * 0.08, left: size * 0.08,
      }} />
    </View>
  );
}

export function Wordmark({ size = 26 }: { size?: number }) {
  const { colors } = useTheme();
  return (
    <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: size, letterSpacing: -0.8 }}>
      FAZ<Text style={{ color: colors.primary }}>Ê</Text>
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
