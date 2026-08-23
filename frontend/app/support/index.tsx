import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { FlatList, Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { EmptyState, Skeleton } from "@/src/components/ui";
import { useRequireAuth } from "@/src/hooks/use-require-auth";
import { useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

type Ticket = { id: string; category: string; subject: string; status: string; updated_at: string };

const STATUS_LABELS: Record<string, string> = {
  OPEN: "Aberto", IN_PROGRESS: "Em andamento", WAITING_USER: "Aguardando você", RESOLVED: "Resolvido", CLOSED: "Fechado",
};

export default function SupportList() {
  const { colors } = useTheme();
  useRequireAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [items, setItems] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);

  useFocusEffect(useCallback(() => {
    api.get("/tickets").then(setItems).catch(() => {}).finally(() => setLoading(false));
  }, []));

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + 8 }}>
      <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: 20, height: 48, gap: 14 }}>
        <Pressable onPress={() => safeBack(router, "/settings")} hitSlop={10}><Ionicons name="arrow-back" size={24} color={colors.ink} /></Pressable>
        <Text style={{ color: colors.ink, fontSize: 18, fontWeight: "800", flex: 1 }}>Meus chamados</Text>
        <Pressable testID="support-new-button" onPress={() => router.push("/support/new")} hitSlop={10}>
          <Ionicons name="add-circle" size={28} color={colors.primary} />
        </Pressable>
      </View>

      {loading ? (
        <View style={{ padding: 20, gap: 10 }}><Skeleton height={72} /><Skeleton height={72} /></View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => item.id}
          contentContainerStyle={{ padding: 20, gap: 10, flexGrow: 1 }}
          renderItem={({ item }) => (
            <Pressable
              testID="support-ticket-row"
              onPress={() => router.push(`/support/${item.id}`)}
              style={({ pressed }) => [{
                flexDirection: "row", alignItems: "center", gap: 12, padding: 16,
                borderRadius: 16, borderWidth: 1, borderColor: colors.border,
                backgroundColor: pressed ? colors.alt : colors.surface,
              }]}
            >
              <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" }}>
                <Ionicons name="chatbox-ellipses-outline" size={18} color={colors.primary} />
              </View>
              <View style={{ flex: 1, gap: 2 }}>
                <Text style={{ color: colors.ink, fontSize: 14, fontWeight: "700" }} numberOfLines={1}>{item.subject}</Text>
                <Text style={{ color: colors.muted, fontSize: 12 }}>{STATUS_LABELS[item.status] || item.status} · {new Date(item.updated_at).toLocaleDateString("pt-BR")}</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.faint} />
            </Pressable>
          )}
          ListEmptyComponent={
            <EmptyState
              icon="chatbox-ellipses-outline"
              title="Nenhum chamado ainda"
              body="Encontrou um problema ou tem uma sugestão? Fale com a gente."
              actionTitle="Abrir chamado"
              onAction={() => router.push("/support/new")}
            />
          }
        />
      )}
    </View>
  );
}
