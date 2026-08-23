import { Ionicons } from "@expo/vector-icons";
import React, { useEffect, useState } from "react";
import { Text, View } from "react-native";

import { adminApi } from "@/src/admin-api";
import { Badge, BadgeTone } from "@/src/components/admin/Badge";
import { Column, Table } from "@/src/components/admin/Table";
import { fonts } from "@/src/hooks/use-app-fonts";
import { radius, space, useTheme } from "@/src/theme";
import { Skeleton } from "@/src/components/ui";

type AdminRow = { id: string; name: string; email: string; role: string; active: boolean; online: boolean; last_active_at: string | null };
type ActionRow = { id: string; admin_id: string; admin_name?: string; action: string; target: string; result?: string; created_at: string };
type Alerts = { tickets_open: number; disputes_open: number; reports_open: number; withdrawals_review: number; risk_flags_critical: number };
type Supervision = { admins: AdminRow[]; recent_actions: ActionRow[]; alerts: Alerts };

const ALERT_TILES: { key: keyof Alerts; label: string; icon: React.ComponentProps<typeof Ionicons>["name"]; level: "critical" | "attention" }[] = [
  { key: "risk_flags_critical", label: "Sinalizações de risco crítico", icon: "shield-outline", level: "critical" },
  { key: "withdrawals_review", label: "Saques em análise", icon: "cash-outline", level: "critical" },
  { key: "disputes_open", label: "Disputas em aberto", icon: "warning-outline", level: "attention" },
  { key: "reports_open", label: "Denúncias abertas", icon: "flag-outline", level: "attention" },
  { key: "tickets_open", label: "Chamados abertos", icon: "chatbox-ellipses-outline", level: "attention" },
];

const ROLE_TONE: Record<string, BadgeTone> = { OWNER: "primary", MANAGER: "amber", SUPPORT: "green", MAINTENANCE: "neutral" };

export default function AdminSupervision() {
  const { colors } = useTheme();
  const [data, setData] = useState<Supervision | null>(null);

  useEffect(() => {
    const load = () => adminApi.get("/admin/supervision").then(setData).catch(() => {});
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, []);

  if (!data) {
    return (
      <View style={{ gap: space.lg }}>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.md }}>
          {Array.from({ length: 5 }).map((_, i) => <View key={i} style={{ width: 220 }}><Skeleton height={96} radius={16} /></View>)}
        </View>
        <Skeleton height={220} radius={16} />
      </View>
    );
  }

  const { admins, recent_actions, alerts } = data;

  const actionColumns: Column<ActionRow>[] = [
    { key: "admin_name", label: "Administrador", render: (a) => <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 13 }}>{a.admin_name || "—"}</Text> },
    { key: "action", label: "Ação", render: (a) => <Text style={{ color: colors.ink, fontFamily: fonts.body, fontSize: 13 }}>{a.action}</Text> },
    { key: "target", label: "Recurso", width: 2, render: (a) => <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 12 }} numberOfLines={1}>{a.target}</Text> },
    { key: "result", label: "Resultado", render: (a) => <Text style={{ color: a.result === "failure" ? colors.danger : colors.green, fontFamily: fonts.bodySemiBold, fontSize: 12 }}>{a.result === "failure" ? "falha" : "sucesso"}</Text> },
    { key: "created_at", label: "Quando", render: (a) => <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 12 }}>{new Date(a.created_at).toLocaleString("pt-BR")}</Text> },
  ];

  const adminColumns: Column<AdminRow>[] = [
    { key: "name", label: "Nome", render: (a) => (
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
        <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: a.online ? colors.green : colors.faint }} />
        <View>
          <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 13 }}>{a.name}</Text>
          <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 11 }}>{a.email}</Text>
        </View>
      </View>
    ) },
    { key: "role", label: "Papel", render: (a) => <Badge label={a.role} tone={ROLE_TONE[a.role] || "neutral"} /> },
    { key: "online", label: "Status", render: (a) => (
      !a.active ? <Badge label="Desativado" tone="neutral" /> : <Badge label={a.online ? "Online" : "Offline"} tone={a.online ? "green" : "neutral"} />
    ) },
    { key: "last_active_at", label: "Última atividade", render: (a) => <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 12 }}>{a.last_active_at ? new Date(a.last_active_at).toLocaleString("pt-BR") : "—"}</Text> },
  ];

  const hasAlerts = ALERT_TILES.some((t) => alerts[t.key] > 0);

  return (
    <View style={{ gap: space.xl }}>
      <View style={{ gap: space.sm }}>
        <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 13 }}>
          {hasAlerts ? "Precisa de atenção" : "Tudo em dia"}
        </Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
          {ALERT_TILES.map((t) => {
            const count = alerts[t.key];
            const active = count > 0;
            const soft = t.level === "critical" ? colors.dangerSoft : colors.accentSoft;
            const fg = t.level === "critical" ? colors.danger : colors.amber;
            return (
              <View
                key={t.key}
                style={{
                  flexDirection: "row", alignItems: "center", gap: 10, minWidth: 200,
                  backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border,
                  borderRadius: radius.lg, paddingVertical: 10, paddingHorizontal: 10,
                }}
              >
                <View style={{ width: 34, height: 34, borderRadius: 17, alignItems: "center", justifyContent: "center", backgroundColor: active ? soft : colors.alt }}>
                  <Ionicons name={t.icon} size={16} color={active ? fg : colors.faint} />
                </View>
                <View style={{ flexShrink: 1 }}>
                  <Text style={{ color: active ? fg : colors.ink, fontFamily: fonts.headingBold, fontSize: 17 }}>{count}</Text>
                  <Text style={{ color: colors.muted, fontFamily: fonts.bodyMedium, fontSize: 12 }} numberOfLines={1}>{t.label}</Text>
                </View>
              </View>
            );
          })}
        </View>
      </View>

      <View style={{ gap: space.sm }}>
        <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 13 }}>Equipe agora</Text>
        <Table columns={adminColumns} rows={admins} emptyIcon="people-outline" emptyLabel="Nenhum administrador cadastrado." />
      </View>

      <View style={{ gap: space.sm }}>
        <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 13 }}>Linha do tempo de ações</Text>
        <Table columns={actionColumns} rows={recent_actions} emptyIcon="document-text-outline" emptyLabel="Nenhuma ação registrada ainda." />
      </View>
    </View>
  );
}
