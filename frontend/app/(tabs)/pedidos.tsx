import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { FlatList, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Order } from "@/src/api";
import BrowseOrders from "@/src/components/BrowseOrders";
import { OrderCard } from "@/src/components/OrderCard";
import { EmptyState, Segmented, Skeleton } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useApp } from "@/src/state";
import { space, useTheme } from "@/src/theme";

const ALL_STATUS = "published,accepted,in_progress,completed,cancelled";

export default function Pedidos() {
  const { colors } = useTheme();
  const { me, mode, setMode } = useApp();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);

  // Cliente mode fetches "meus pedidos" here — same query shape as activity.tsx's
  // "orders" tab, which stays untouched (it still covers jobs/favorites/reviews).
  useFocusEffect(useCallback(() => {
    if (mode !== "client" || !me) return;
    setLoading(true);
    api.get(`/orders?client_id=${me.id}&status=${ALL_STATUS}`).then(setOrders).catch(() => {}).finally(() => setLoading(false));
  }, [mode, me]));

  if (mode === "worker") return <BrowseOrders />;

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + space.md }}>
      <View style={{ paddingHorizontal: space.xl, gap: space.md }}>
        <Segmented
          options={[{ key: "client", label: "Preciso de ajuda" }, { key: "worker", label: "Quero fazer" }]}
          value={mode}
          onChange={setMode}
        />
        <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 24, letterSpacing: -0.5 }}>Meus pedidos</Text>
      </View>
      {loading ? (
        <View style={{ padding: space.xl, gap: 10 }}><Skeleton /><Skeleton /></View>
      ) : (
        <FlatList
          data={orders}
          keyExtractor={(item) => item.id}
          contentContainerStyle={{ padding: space.xl, gap: 10, flexGrow: 1 }}
          renderItem={({ item, index }) => <OrderCard order={item} index={index} showStatus onPress={() => router.push(`/order/${item.id}`)} />}
          ListEmptyComponent={<EmptyState icon="document-text-outline" title="Você ainda não publicou nenhum pedido." actionTitle="Publicar pedido" onAction={() => router.push("/create")} />}
        />
      )}
    </View>
  );
}
