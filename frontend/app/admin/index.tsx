import { Ionicons } from "@expo/vector-icons";
import React, { useEffect, useState } from "react";
import { Text, View } from "react-native";

import { adminApi } from "@/src/admin-api";
import { fonts } from "@/src/hooks/use-app-fonts";
import { radius, space, useTheme } from "@/src/theme";
import { Skeleton } from "@/src/components/ui";

type Overview = {
  users: number; orders: number; orders_open: number; proposals: number; reviews: number;
  reports_open: number; risk_flags_open: number; categories: number; neighborhoods: number;
  withdrawals_pending: number; disputes_open: number;
};

const ALERT_METRICS: { key: keyof Overview; label: string; icon: React.ComponentProps<typeof Ionicons>["name"] }[] = [
  { key: "withdrawals_pending", label: "Saques pendentes", icon: "cash-outline" },
  { key: "disputes_open", label: "Disputas em aberto", icon: "warning-outline" },
  { key: "reports_open", label: "Denúncias abertas", icon: "flag-outline" },
  { key: "risk_flags_open", label: "Sinalizações de risco", icon: "shield-outline" },
];

const OVERVIEW_METRICS: { key: keyof Overview; label: string; icon: React.ComponentProps<typeof Ionicons>["name"] }[] = [
  { key: "users", label: "Usuários cadastrados", icon: "people-outline" },
  { key: "orders", label: "Pedidos totais", icon: "briefcase-outline" },
  { key: "orders_open", label: "Pedidos publicados", icon: "megaphone-outline" },
  { key: "proposals", label: "Propostas enviadas", icon: "chatbox-ellipses-outline" },
  { key: "reviews", label: "Avaliações", icon: "star-outline" },
  { key: "categories", label: "Categorias ativas", icon: "pricetags-outline" },
  { key: "neighborhoods", label: "Bairros cadastrados", icon: "location-outline" },
];

export default function AdminDashboard() {
  const { colors } = useTheme();
  const [data, setData] = useState<Overview | null>(null);

  useEffect(() => {
    adminApi.get("/admin/overview").then(setData).catch(() => {});
  }, []);

  if (!data) {
    return (
      <View style={{ gap: space.lg }}>
        <Skeleton height={72} radius={14} />
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
          {Array.from({ length: 7 }).map((_, i) => <View key={i} style={{ width: 168 }}><Skeleton height={78} radius={12} /></View>)}
        </View>
      </View>
    );
  }

  const hasAlerts = ALERT_METRICS.some((m) => data[m.key] > 0);

  return (
    <View style={{ gap: space.xl }}>
      <View style={{ gap: space.sm }}>
        <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 13 }}>
          {hasAlerts ? "Precisa de atenção" : "Tudo em dia"}
        </Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
          {ALERT_METRICS.map((m) => {
            const count = data[m.key];
            const active = count > 0;
            return (
              <View
                key={m.key}
                style={{
                  flexDirection: "row", alignItems: "center", gap: 10, minWidth: 200,
                  backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border,
                  borderRadius: radius.lg, paddingVertical: 10, paddingHorizontal: 10,
                }}
              >
                <View style={{
                  width: 34, height: 34, borderRadius: 17, alignItems: "center", justifyContent: "center",
                  backgroundColor: active ? colors.dangerSoft : colors.alt,
                }}>
                  <Ionicons name={m.icon} size={16} color={active ? colors.danger : colors.faint} />
                </View>
                <View style={{ flexShrink: 1 }}>
                  <Text style={{ color: active ? colors.danger : colors.ink, fontFamily: fonts.headingBold, fontSize: 17 }}>{count}</Text>
                  <Text style={{ color: colors.muted, fontFamily: fonts.bodyMedium, fontSize: 12 }} numberOfLines={1}>{m.label}</Text>
                </View>
              </View>
            );
          })}
        </View>
      </View>

      <View style={{ gap: space.sm }}>
        <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 13 }}>Visão geral</Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
          {OVERVIEW_METRICS.map((m) => (
            <View
              key={m.key}
              style={{
                width: 168, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border,
                borderRadius: radius.lg, padding: space.md, gap: 8,
              }}
            >
              <View style={{ width: 30, height: 30, borderRadius: 15, alignItems: "center", justifyContent: "center", backgroundColor: colors.primarySoft }}>
                <Ionicons name={m.icon} size={14} color={colors.primary} />
              </View>
              <Text style={{ color: colors.ink, fontFamily: fonts.headingBold, fontSize: 21 }}>{data[m.key]}</Text>
              <Text style={{ color: colors.muted, fontFamily: fonts.bodyMedium, fontSize: 12 }} numberOfLines={2}>{m.label}</Text>
            </View>
          ))}
        </View>
      </View>
    </View>
  );
}
