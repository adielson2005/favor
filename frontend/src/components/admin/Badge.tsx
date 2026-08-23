import React from "react";
import { Text, View } from "react-native";

import { fonts } from "@/src/hooks/use-app-fonts";
import { useTheme } from "@/src/theme";

export type BadgeTone = "neutral" | "green" | "amber" | "danger" | "primary";

export function Badge({ label, tone = "neutral" }: { label: string; tone?: BadgeTone }) {
  const { colors } = useTheme();
  const map: Record<BadgeTone, { bg: string; fg: string }> = {
    neutral: { bg: colors.alt, fg: colors.muted },
    green: { bg: colors.greenSoft, fg: colors.green },
    amber: { bg: colors.accentSoft, fg: colors.amber },
    danger: { bg: colors.dangerSoft, fg: colors.danger },
    primary: { bg: colors.primarySoft, fg: colors.primary },
  };
  const { bg, fg } = map[tone];
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 5, backgroundColor: bg, paddingHorizontal: 9, height: 22, borderRadius: 7, alignSelf: "flex-start" }}>
      <View style={{ width: 5, height: 5, borderRadius: 2.5, backgroundColor: fg }} />
      <Text style={{ color: fg, fontFamily: fonts.bodySemiBold, fontSize: 11.5 }}>{label}</Text>
    </View>
  );
}
