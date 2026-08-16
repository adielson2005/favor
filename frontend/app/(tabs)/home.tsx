import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Order } from "@/src/api";
import { OrderCard } from "@/src/components/OrderCard";
import { Avatar, Btn, EmptyState, Segmented, Skeleton } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useBreakpoint } from "@/src/hooks/use-breakpoint";
import { useApp } from "@/src/state";
import { useTheme } from "@/src/theme";

export default function Home() {
  const { colors } = useTheme();
  const { me, mode, setMode, categories, city, unread, refreshUnread, loading: bootLoading, error, retry } = useApp();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { isDesktop } = useBreakpoint();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    if (!city || !me) return;
    try {
      const query = mode === "client" ? `client_id=${me.id}&status=published,accepted,in_progress` : `city_id=${city.id}&status=published`;
      const data = await api.get(`/orders?${query}&limit=20`);
      setOrders(mode === "worker" ? data.filter((o: Order) => o.client_id !== me.id) : data);
    } catch { /* handled by empty state */ } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [mode, me, city]);

  useFocusEffect(useCallback(() => { load(); refreshUnread(); }, [load, refreshUnread]));

  if (error) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, justifyContent: "center" }}>
        <EmptyState icon="cloud-offline-outline" title="Não conseguimos carregar isso agora." body="Verifique sua conexão e tente novamente." actionTitle="Tentar novamente" onAction={retry} />
      </View>
    );
  }

  if (!me) {
    return <View style={{ flex: 1, backgroundColor: colors.bg }} />;
  }

  const isClient = mode === "client";
  const nearby = orders.slice(0, 3);

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView
        contentContainerStyle={{ paddingTop: insets.top + 16, paddingBottom: 32, width: "100%", maxWidth: isDesktop ? 720 : undefined, alignSelf: "center" }}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={colors.muted} />}
      >
        {/* Header */}
        <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: 20, gap: 12 }}>
          <View style={{ flex: 1 }}>
            <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 22, letterSpacing: -0.5 }}>Olá, {me.name.split(" ")[0]}</Text>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 4, marginTop: 2 }}>
              <Ionicons name="location-outline" size={13} color={colors.muted} />
              <Text style={{ color: colors.muted, fontSize: 13 }}>{city?.name || "Parauapebas"}, PA</Text>
            </View>
          </View>
          <Pressable testID="notifications-button" onPress={() => router.push("/notifications")} hitSlop={6} style={{ width: 42, height: 42, borderRadius: 21, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center" }}>
            <Ionicons name="notifications-outline" size={19} color={colors.ink} />
            {unread > 0 && <View style={{ position: "absolute", top: 8, right: 9, width: 9, height: 9, borderRadius: 5, backgroundColor: colors.danger, borderWidth: 1.5, borderColor: colors.surface }} />}
          </Pressable>
          <Pressable onPress={() => router.push("/(tabs)/profile")}>
            <Avatar name={me.name} initials={me.initials} size={42} />
          </Pressable>
        </View>

        {/* Email verification nudge — non-blocking, dismiss by verifying or ignoring */}
        {!me.verified_email && (
          <Pressable
            testID="verify-email-banner"
            onPress={() => router.push("/auth/verify-email")}
            style={{ flexDirection: "row", alignItems: "center", gap: 10, marginHorizontal: 20, marginTop: 14, padding: 12, borderRadius: 14, backgroundColor: colors.accentSoft }}
          >
            <Ionicons name="mail-unread-outline" size={18} color={colors.accent} />
            <Text style={{ flex: 1, color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 13 }}>Confirme seu e-mail para proteger sua conta.</Text>
            <Ionicons name="chevron-forward" size={16} color={colors.faint} />
          </Pressable>
        )}

        {/* Mode switch */}
        <View style={{ paddingHorizontal: 20, marginTop: 18 }}>
          <Segmented
            options={[{ key: "client", label: "Preciso de ajuda" }, { key: "worker", label: "Quero fazer" }]}
            value={mode}
            onChange={(m) => { setMode(m); setLoading(true); }}
          />
        </View>

        {/* Hero */}
        <View style={{ paddingHorizontal: 20, marginTop: 26 }}>
          <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 26, letterSpacing: -0.7, lineHeight: 32 }}>
            {isClient ? "Precisa de uma mão?" : "Encontre algo para fazer."}
          </Text>
          {isClient ? (
            <View style={{ marginTop: 16, gap: 12 }}>
              <Pressable
                testID="home-need-input"
                onPress={() => router.push("/create")}
                style={({ pressed }) => [{ flexDirection: "row", alignItems: "center", gap: 10, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 16, paddingHorizontal: 16, height: 54, opacity: pressed ? 0.7 : 1 }]}
              >
                <Ionicons name="search-outline" size={18} color={colors.faint} />
                <Text style={{ color: colors.faint, fontSize: 15 }}>O que você precisa?</Text>
              </Pressable>
              <Btn testID="home-ask-help-button" title="Pedir ajuda" icon="arrow-forward" onPress={() => router.push("/create")} />
            </View>
          ) : (
            <View style={{ marginTop: 16 }}>
              <Btn testID="home-explore-button" title="Ver pedidos disponíveis" icon="compass-outline" onPress={() => router.push("/(tabs)/explore")} variant="primary" />
            </View>
          )}
        </View>

        {/* Categories */}
        <View style={{ marginTop: 30 }}>
          <View style={{ paddingHorizontal: 20 }}>
            <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 17, marginBottom: 12 }}>Categorias</Text>
          </View>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 20, gap: 10 }}>
            {bootLoading
              ? [1, 2, 3, 4].map((i) => <View key={i} style={{ width: 88 }}><Skeleton height={86} radius={16} /></View>)
              : categories.map((cat) => (
                <Pressable
                  key={cat.id}
                  testID={`category-${cat.id}`}
                  onPress={() => router.push({ pathname: "/(tabs)/explore", params: { category: cat.id } })}
                  style={({ pressed }) => [{ width: 88, paddingVertical: 14, borderRadius: 16, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, alignItems: "center", gap: 8, opacity: pressed ? 0.7 : 1 }]}
                >
                  <Ionicons name={cat.icon as keyof typeof Ionicons.glyphMap} size={21} color={colors.primary} />
                  <Text style={{ color: colors.ink, fontSize: 11, fontWeight: "600", textAlign: "center" }} numberOfLines={1}>{cat.name.split(" ")[0]}</Text>
                </Pressable>
              ))}
          </ScrollView>
        </View>

        {/* Orders */}
        <View style={{ paddingHorizontal: 20, marginTop: 30 }}>
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
            <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 17 }}>{isClient ? "Seus pedidos" : "Pedidos perto de você"}</Text>
            <Pressable testID="see-all-button" onPress={() => router.push(isClient ? "/activity" : "/(tabs)/explore")} hitSlop={8}>
              <Text style={{ color: colors.primary, fontSize: 13, fontWeight: "700" }}>Ver todos</Text>
            </Pressable>
          </View>
          {loading ? (
            <View style={{ gap: 10 }}><Skeleton /><Skeleton /></View>
          ) : nearby.length === 0 ? (
            isClient
              ? <EmptyState icon="document-text-outline" title="Você ainda não publicou nenhum pedido." actionTitle="Publicar pedido" onAction={() => router.push("/create")} />
              : <EmptyState icon="leaf-outline" title="Nenhum pedido por perto agora." body="Volte mais tarde ou explore outras categorias." />
          ) : (
            <View style={{ gap: 10 }}>
              {nearby.map((order, i) => <OrderCard key={order.id} order={order} index={i} showStatus={isClient} onPress={() => router.push(`/order/${order.id}`)} />)}
            </View>
          )}
        </View>
      </ScrollView>
    </View>
  );
}
