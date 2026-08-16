import { Ionicons } from "@expo/vector-icons";
import React from "react";
import { Pressable, StyleProp, Text, View, ViewStyle } from "react-native";
import Animated, { FadeInDown } from "react-native-reanimated";

import { Order } from "@/src/api";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useTheme } from "@/src/theme";

// Pure/props-driven — memoized so re-rendering a parent list (search debounce,
// refresh, filter change) doesn't re-render every card, only the ones whose data changed.
export const OrderCard = React.memo(function OrderCard({ order, onPress, showStatus, index = 0, style }: { order: Order; onPress: () => void; showStatus?: boolean; index?: number; style?: StyleProp<ViewStyle> }) {
  const { colors } = useTheme();
  const statusColor = order.status === "completed" ? colors.green : order.status === "cancelled" ? colors.danger : order.status === "published" ? colors.muted : colors.primary;
  return (
    <Animated.View style={style} entering={FadeInDown.duration(260).delay(Math.min(index, 8) * 40)}>
      <Pressable
        testID="order-card"
        onPress={onPress}
        style={({ pressed }) => [{
          backgroundColor: colors.surface, borderRadius: 18, padding: 16, gap: 10,
          borderWidth: 1, borderColor: colors.border, opacity: pressed ? 0.75 : 1,
        }]}
      >
        <View style={{ flexDirection: "row", gap: 12, alignItems: "flex-start" }}>
          <View style={{ width: 42, height: 42, borderRadius: 13, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" }}>
            <Ionicons name={(order.category?.icon || "sparkles-outline") as keyof typeof Ionicons.glyphMap} size={19} color={colors.primary} />
          </View>
          <View style={{ flex: 1, gap: 3 }}>
            <Text style={{ color: colors.ink, fontFamily: fonts.bodyBold, fontSize: 15 }} numberOfLines={1}>{order.title}</Text>
            <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 13, lineHeight: 18 }} numberOfLines={1}>{order.description}</Text>
          </View>
          <Text style={{ color: colors.green, fontFamily: fonts.headingBold, fontSize: 15 }}>R$ {order.budget}</Text>
        </View>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <Meta icon="location-outline" text={order.neighborhood || order.city || ""} />
          <Meta icon="time-outline" text={`${order.date_label}${order.time_label ? ` · ${order.time_label}` : ""}`} />
          <View style={{ flex: 1 }} />
          {showStatus ? (
            <Text style={{ color: statusColor, fontFamily: fonts.bodyBold, fontSize: 12 }}>{order.status_label}</Text>
          ) : (
            <Text style={{ color: colors.faint, fontFamily: fonts.bodySemiBold, fontSize: 12 }}>{order.type === "favor" ? "Favor" : "Serviço"}</Text>
          )}
        </View>
      </Pressable>
    </Animated.View>
  );
});

function Meta({ icon, text }: { icon: keyof typeof Ionicons.glyphMap; text: string }) {
  const { colors } = useTheme();
  if (!text) return null;
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
      <Ionicons name={icon} size={13} color={colors.faint} />
      <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 12 }}>{text}</Text>
    </View>
  );
}
