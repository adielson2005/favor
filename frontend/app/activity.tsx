import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { FlatList, Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Order } from "@/src/api";
import { OrderCard } from "@/src/components/OrderCard";
import { Avatar, Chip, EmptyState, Skeleton, Stars } from "@/src/components/ui";
import { useRequireAuth } from "@/src/hooks/use-require-auth";
import { useApp } from "@/src/state";
import { useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

type TabKey = "orders" | "jobs" | "favorites" | "reviews";
const TABS: { key: TabKey; label: string }[] = [
  { key: "orders", label: "Meus pedidos" },
  { key: "jobs", label: "Meus serviços" },
  { key: "favorites", label: "Favoritos" },
  { key: "reviews", label: "Avaliações" },
];
const ALL_STATUS = "published,accepted,in_progress,completed,cancelled";

export default function Activity() {
  const { colors } = useTheme();
  const { me } = useApp();
  useRequireAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{ tab?: TabKey }>();
  const [tab, setTab] = useState<TabKey>(params.tab || "orders");
  const [orders, setOrders] = useState<Order[]>([]);
  const [reviews, setReviews] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!me) return;
    setLoading(true);
    try {
      if (tab === "orders") setOrders(await api.get(`/orders?client_id=${me.id}&status=${ALL_STATUS}`));
      else if (tab === "jobs") setOrders(await api.get(`/orders?worker_id=${me.id}&status=${ALL_STATUS}`));
      else if (tab === "favorites") setOrders((await api.get(`/favorites`)).orders);
      else setReviews(await api.get(`/users/${me.id}/reviews`));
    } catch { /* empty state shown */ } finally { setLoading(false); }
  }, [tab, me]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const empty = {
    orders: { icon: "document-text-outline" as const, title: "Você ainda não publicou nenhum pedido.", action: "Publicar pedido", go: () => router.push("/create") },
    jobs: { icon: "construct-outline" as const, title: "Você ainda não realizou serviços.", action: "Explorar pedidos", go: () => router.push("/(tabs)/explore") },
    favorites: { icon: "heart-outline" as const, title: "Nenhum favorito ainda.", action: "Explorar pedidos", go: () => router.push("/(tabs)/explore") },
    reviews: { icon: "star-outline" as const, title: "Nenhuma avaliação por enquanto.", action: undefined, go: undefined },
  }[tab];

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + 8 }}>
      <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: 20, height: 48, gap: 14 }}>
        <Pressable onPress={() => safeBack(router, "/(tabs)/profile")} hitSlop={10}><Ionicons name="arrow-back" size={24} color={colors.ink} /></Pressable>
        <Text style={{ color: colors.ink, fontSize: 18, fontWeight: "800" }}>Minha atividade</Text>
      </View>
      <View style={{ marginTop: 6, marginBottom: 4 }}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 20, gap: 8, paddingVertical: 8 }}>
          {TABS.map((t) => <Chip key={t.key} testID={`activity-tab-${t.key}`} label={t.label} active={tab === t.key} onPress={() => setTab(t.key)} />)}
        </ScrollView>
      </View>
      {loading ? (
        <View style={{ padding: 20, gap: 10 }}><Skeleton /><Skeleton /></View>
      ) : tab === "reviews" ? (
        <FlatList
          data={reviews}
          keyExtractor={(item) => item.id}
          contentContainerStyle={{ padding: 20, gap: 10, flexGrow: 1 }}
          renderItem={({ item }) => (
            <View style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 16, padding: 14, gap: 8 }}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
                <Avatar name={item.author?.name} initials={item.author?.initials} size={36} />
                <View style={{ flex: 1 }}>
                  <Text style={{ color: colors.ink, fontSize: 14, fontWeight: "700" }}>{item.author?.name || "Usuário"}</Text>
                  <Stars value={item.stars} size={12} />
                </View>
              </View>
              {item.comment ? <Text style={{ color: colors.muted, fontSize: 13, lineHeight: 19 }}>{item.comment}</Text> : null}
            </View>
          )}
          ListEmptyComponent={<EmptyState icon={empty.icon} title={empty.title} />}
        />
      ) : (
        <FlatList
          data={orders}
          keyExtractor={(item) => item.id}
          contentContainerStyle={{ padding: 20, gap: 10, flexGrow: 1 }}
          renderItem={({ item, index }) => <OrderCard order={item} index={index} showStatus onPress={() => router.push(`/order/${item.id}`)} />}
          ListEmptyComponent={<EmptyState icon={empty.icon} title={empty.title} actionTitle={empty.action} onAction={empty.go} />}
        />
      )}
    </View>
  );
}
