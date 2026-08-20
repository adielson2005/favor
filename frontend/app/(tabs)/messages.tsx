import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { FlatList, Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Message, Order, User } from "@/src/api";
import { Avatar, EmptyState, Skeleton } from "@/src/components/ui";
import { useBreakpoint } from "@/src/hooks/use-breakpoint";
import { useApp } from "@/src/state";
import { useTheme } from "@/src/theme";

type Conversation = { order: Order; other: User | null; last_message: Message | null };

export default function Messages() {
  const { colors } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { isDesktop } = useBreakpoint();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);

  useFocusEffect(useCallback(() => {
    api.get(`/conversations`).then(setConversations).catch(() => {}).finally(() => setLoading(false));
  }, []));

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + 12 }}>
      <View style={{ paddingHorizontal: 20, marginBottom: 12, width: "100%", maxWidth: isDesktop ? 720 : undefined, alignSelf: "center" }}>
        <Text style={{ color: colors.ink, fontSize: 24, fontWeight: "800", letterSpacing: -0.5 }}>Mensagens</Text>
      </View>
      {loading ? (
        <View style={{ padding: 20, gap: 10, width: "100%", maxWidth: isDesktop ? 720 : undefined, alignSelf: "center" }}><Skeleton height={68} /><Skeleton height={68} /></View>
      ) : (
        <FlatList
          data={conversations}
          keyExtractor={(item) => item.order.id}
          contentContainerStyle={{ paddingBottom: 32, flexGrow: 1, width: "100%", maxWidth: isDesktop ? 720 : undefined, alignSelf: "center" }}
          renderItem={({ item }) => (
            <Pressable
              testID="conversation-row"
              onPress={() => router.push(`/chat/${item.order.id}`)}
              style={({ pressed }) => [{ flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 20, paddingVertical: 14, backgroundColor: pressed ? colors.alt : "transparent" }]}
            >
              <Avatar name={item.other?.name} initials={item.other?.initials} size={48} />
              <View style={{ flex: 1, gap: 2 }}>
                <Text style={{ color: colors.ink, fontSize: 15, fontWeight: "700" }}>{item.other?.name || "Usuário"}</Text>
                <Text style={{ color: colors.muted, fontSize: 13 }} numberOfLines={1}>
                  {item.last_message ? (item.last_message.type === "image" ? "📷 Imagem" : item.last_message.text) : item.order.title}
                </Text>
              </View>
              <View style={{ alignItems: "flex-end", gap: 4 }}>
                <Text style={{ color: item.order.status === "completed" ? colors.green : colors.primary, fontSize: 11, fontWeight: "700" }}>{item.order.status_label}</Text>
              </View>
            </Pressable>
          )}
          ItemSeparatorComponent={() => <View style={{ height: 1, backgroundColor: colors.border, marginLeft: 80 }} />}
          ListEmptyComponent={
            <EmptyState
              icon="chatbubbles-outline"
              title="Nenhuma conversa por enquanto."
              body="Quando uma proposta for aceita, a conversa aparece aqui."
              actionTitle="Explorar pedidos"
              onAction={() => router.push("/(tabs)/explore")}
            />
          }
        />
      )}
    </View>
  );
}
