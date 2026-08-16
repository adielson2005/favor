import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useMemo, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Wallet, WalletTransaction } from "@/src/api";
import { Skeleton } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useRequireAuth } from "@/src/hooks/use-require-auth";
import { radius, space, type, useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

function startOf(period: "day" | "week" | "month"): Date {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  if (period === "week") d.setDate(d.getDate() - d.getDay());
  if (period === "month") d.setDate(1);
  return d;
}

export default function Earnings() {
  const { colors } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  useRequireAuth();

  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [earnings, setEarnings] = useState<WalletTransaction[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [w, txns] = await Promise.all([api.get("/wallet"), api.get("/wallet/transactions?type=EARNING&limit=100")]);
      setWallet(w);
      setEarnings(txns);
    } catch { /* keep last */ } finally { setLoading(false); }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const totals = useMemo(() => {
    const dayStart = startOf("day"), weekStart = startOf("week"), monthStart = startOf("month");
    let today = 0, week = 0, month = 0, total = 0;
    for (const t of earnings) {
      const created = new Date(t.created_at);
      total += t.amount;
      if (created >= monthStart) month += t.amount;
      if (created >= weekStart) week += t.amount;
      if (created >= dayStart) today += t.amount;
    }
    return { today, week, month, total };
  }, [earnings]);

  const fmt = (v: number) => `R$ ${v.toFixed(2).replace(".", ",")}`;

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + space.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: space.xl, height: 48, gap: space.md }}>
        <Pressable testID="earnings-back-button" onPress={() => safeBack(router, "/wallet")} hitSlop={10}>
          <Ionicons name="arrow-back" size={24} color={colors.ink} />
        </Pressable>
        <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 17, flex: 1 }}>Meus ganhos</Text>
      </View>

      {loading ? (
        <View style={{ padding: space.xl, gap: space.md }}><Skeleton height={100} /><Skeleton height={100} /></View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: space.xl, gap: space.lg }}>
          <View style={{ backgroundColor: colors.primary, borderRadius: radius.xl, padding: space.xl, gap: space.xs }}>
            <Text style={{ color: "rgba(255,255,255,0.72)", ...type.micro }}>Disponível para saque</Text>
            <Text style={{ color: "#FFFFFF", fontFamily: fonts.headingExtraBold, fontSize: 36 }}>{fmt(wallet?.available || 0)}</Text>
          </View>

          <View style={{ flexDirection: "row", gap: space.sm }}>
            <StatCard label="Pendente" value={fmt(wallet?.pending || 0)} />
            <StatCard label="Em serviços ativos" value={fmt(wallet?.processing || 0)} />
          </View>

          <View style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: space.lg, gap: space.md }}>
            <PeriodRow label="Hoje" value={fmt(totals.today)} />
            <PeriodRow label="Esta semana" value={fmt(totals.week)} />
            <PeriodRow label="Este mês" value={fmt(totals.month)} />
            <View style={{ height: 1, backgroundColor: colors.border }} />
            <PeriodRow label="Total ganho" value={fmt(totals.total)} strong />
          </View>
        </ScrollView>
      )}
    </View>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  const { colors } = useTheme();
  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: space.lg, gap: 4 }}>
      <Text style={{ color: colors.faint, ...type.micro }}>{label}</Text>
      <Text style={{ color: colors.ink, fontFamily: fonts.headingBold, fontSize: 18 }}>{value}</Text>
    </View>
  );
}

function PeriodRow({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
      <Text style={{ color: colors.muted, fontSize: strong ? 15 : 14, fontFamily: strong ? fonts.bodyBold : fonts.body }}>{label}</Text>
      <Text style={{ color: colors.ink, fontFamily: strong ? fonts.headingBold : fonts.bodySemiBold, fontSize: strong ? 17 : 14 }}>{value}</Text>
    </View>
  );
}
