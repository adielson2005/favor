import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useEffect, useState } from "react";
import { FlatList, Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { EmptyState, Skeleton } from "@/src/components/ui";
import { useApp } from "@/src/state";
import { useTheme } from "@/src/theme";

const ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  proposal: "mail-outline", accept: "checkmark-circle-outline", message: "chatbubble-outline",
  status: "flag-outline", review: "star-outline",
};

export default function Notifications() {
  const { colors } = useTheme();
  const { me, refreshUnread } = useApp();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/notifications?user_id=${me.id}`)
      .then((d) => setItems(d.items || []))
      .catch(() => {})
      .finally(() => setLoading(false));
    api.post(`/notifications/read?user_id=${me.id}`).then(refreshUnread).catch(() => {});
  }, [me.id, refreshUnread]);

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + 8 }}>
      <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: 20, height: 48, gap: 14 }}>
        <Pressable onPress={() => router.back()} hitSlop={10}><Ionicons name="arrow-back" size={24} color={colors.ink} /></Pressable>
        <Text style={{ color: colors.ink, fontSize: 18, fontWeight: "800" }}>Notificações</Text>
      </View>
      {loading ? (
        <View style={{ padding: 20, gap: 10 }}><Skeleton height={64} /><Skeleton height={64} /></View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => item.id}
          contentContainerStyle={{ paddingVertical: 8, flexGrow: 1 }}
          renderItem={({ item }) => (
            <Pressable
              onPress={() => item.order_id && router.push(`/order/${item.order_id}`)}
              style={({ pressed }) => [{ flexDirection: "row", gap: 14, paddingHorizontal: 20, paddingVertical: 14, backgroundColor: pressed ? colors.alt : item.read ? "transparent" : colors.surface }]}
            >
              <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" }}>
                <Ionicons name={ICONS[item.type] || "notifications-outline"} size={18} color={colors.primary} />
              </View>
              <View style={{ flex: 1, gap: 2 }}>
                <Text style={{ color: colors.ink, fontSize: 14, fontWeight: "700" }}>{item.title}</Text>
                <Text style={{ color: colors.muted, fontSize: 13 }} numberOfLines={2}>{item.body}</Text>
              </View>
            </Pressable>
          )}
          ItemSeparatorComponent={() => <View style={{ height: 1, backgroundColor: colors.border, marginLeft: 74 }} />}
          ListEmptyComponent={<EmptyState icon="notifications-off-outline" title="Nada por aqui." body="Avisaremos quando algo importante acontecer." />}
        />
      )}
    </View>
  );
}
