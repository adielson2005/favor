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
