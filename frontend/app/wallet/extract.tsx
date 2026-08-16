import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { FlatList, Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, WalletTransaction } from "@/src/api";
import { TransactionRow } from "@/src/components/WalletComponents";
import { Chip, EmptyState, Sheet, Skeleton } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useRequireAuth } from "@/src/hooks/use-require-auth";
import { radius, space, type, useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

const FILTERS = [
  { key: "all", label: "Todos" },
  { key: "in", label: "Entradas" },
  { key: "out", label: "Saídas" },
  { key: "pending", label: "Pendentes" },
  { key: "completed", label: "Concluídos" },
] as const;

const TYPE_LABELS: Record<string, string> = {
  DEPOSIT: "Depósito", PAYMENT: "Pagamento", COMMISSION: "Comissão", EARNING: "Ganho",
  REFUND: "Reembolso", WITHDRAWAL: "Saque", ADJUSTMENT: "Ajuste",
};
const STATUS_LABELS: Record<string, string> = {
  PENDING: "Pendente", PROCESSING: "Processando", COMPLETED: "Concluído", FAILED: "Falhou", CANCELLED: "Cancelado",
};

export default function Extract() {
  const { colors } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  useRequireAuth();

  const [items, setItems] = useState<WalletTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["key"]>("all");
  const [selected, setSelected] = useState<WalletTransaction | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: "100" });
      if (filter === "in") params.set("direction", "IN");
      if (filter === "out") params.set("direction", "OUT");
      if (filter === "pending") params.set("status", "PENDING");
      if (filter === "completed") params.set("status", "COMPLETED");
      setItems(await api.get(`/wallet/transactions?${params.toString()}`));
    } catch { setItems([]); } finally { setLoading(false); }
  }, [filter]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + space.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: space.xl, height: 48, gap: space.md }}>
        <Pressable testID="extract-back-button" onPress={() => safeBack(router, "/wallet")} hitSlop={10}>
          <Ionicons name="arrow-back" size={24} color={colors.ink} />
        </Pressable>
        <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 17, flex: 1 }}>Extrato</Text>
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: space.xl, gap: space.sm, paddingVertical: space.md }}>
        {FILTERS.map((f) => <Chip key={f.key} testID={`extract-filter-${f.key}`} label={f.label} active={filter === f.key} onPress={() => setFilter(f.key)} />)}
      </ScrollView>

      {loading ? (
        <View style={{ padding: space.xl, gap: space.sm }}><Skeleton /><Skeleton /><Skeleton /></View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(t) => t.id}
          contentContainerStyle={{ padding: space.xl, paddingTop: 0, gap: space.sm }}
          renderItem={({ item }) => (
            <Pressable testID="extract-item" onPress={() => setSelected(item)}>
              <TransactionRow txn={item} />
            </Pressable>
          )}
          ListEmptyComponent={<EmptyState icon="receipt-outline" title="Nenhuma movimentação." body="Suas transações aparecerão aqui." />}
        />
      )}

      <Sheet visible={!!selected} onClose={() => setSelected(null)} title="Detalhe da transação">
        {selected && (
          <View style={{ gap: space.md, paddingVertical: space.md, paddingBottom: space.xxl }}>
            <DetailRow label="Tipo" value={TYPE_LABELS[selected.type] || selected.type} />
            <DetailRow label="Valor" value={`R$ ${selected.amount.toFixed(2).replace(".", ",")}`} />
            <DetailRow label="Data" value={new Date(selected.created_at).toLocaleString("pt-BR")} />
            <DetailRow label="Status" value={STATUS_LABELS[selected.status] || selected.status} />
            <DetailRow label="Método" value={selected.provider || "Carteira FAZÊ"} />
            <DetailRow label="ID da transação" value={selected.id} mono />
          </View>
        )}
      </Sheet>
    </View>
  );
}

function DetailRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", justifyContent: "space-between", gap: space.md }}>
      <Text style={{ color: colors.muted, fontSize: 13 }}>{label}</Text>
      <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: mono ? 11 : 13, flexShrink: 1, textAlign: "right" }} numberOfLines={mono ? 1 : undefined}>{value}</Text>
    </View>
  );
}
