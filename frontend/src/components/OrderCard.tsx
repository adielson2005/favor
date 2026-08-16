import { Ionicons } from "@expo/vector-icons";
import React from "react";
import { Pressable, Text, View } from "react-native";

import { Order } from "@/src/api";
import { useTheme } from "@/src/theme";

export function OrderCard({ order, onPress, showStatus }: { order: Order; onPress: () => void; showStatus?: boolean }) {
  const { colors } = useTheme();
  const statusColor = order.status === "completed" ? colors.green : order.status === "cancelled" ? colors.danger : order.status === "published" ? colors.muted : colors.primary;
  return (
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
          <Text style={{ color: colors.ink, fontSize: 15, fontWeight: "700" }} numberOfLines={1}>{order.title}</Text>
          <Text style={{ color: colors.muted, fontSize: 13, lineHeight: 18 }} numberOfLines={1}>{order.description}</Text>
        </View>
        <Text style={{ color: colors.green, fontSize: 15, fontWeight: "800" }}>R$ {order.budget}</Text>
      </View>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <Meta icon="location-outline" text={order.neighborhood || order.city || ""} />
        <Meta icon="time-outline" text={`${order.date_label}${order.time_label ? ` · ${order.time_label}` : ""}`} />
        <View style={{ flex: 1 }} />
        {showStatus ? (
          <Text style={{ color: statusColor, fontSize: 12, fontWeight: "700" }}>{order.status_label}</Text>
        ) : (
          <Text style={{ color: colors.faint, fontSize: 12, fontWeight: "600" }}>{order.type === "favor" ? "Favor" : "Serviço"}</Text>
        )}
      </View>
    </Pressable>
  );
}

function Meta({ icon, text }: { icon: keyof typeof Ionicons.glyphMap; text: string }) {
  const { colors } = useTheme();
  if (!text) return null;
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
      <Ionicons name={icon} size={13} color={colors.faint} />
      <Text style={{ color: colors.muted, fontSize: 12 }}>{text}</Text>
    </View>
  );
}
