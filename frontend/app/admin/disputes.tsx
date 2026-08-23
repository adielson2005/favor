import React, { useCallback, useEffect, useState } from "react";
import { Alert, Text, View } from "react-native";

import { hasPermission } from "@/src/admin-api";
import { useAdminAuth } from "@/src/admin-auth";
import { adminApi } from "@/src/admin-api";
import { AdminSelect } from "@/src/components/admin/AdminSelect";
import { Badge, BadgeTone } from "@/src/components/admin/Badge";
import { Drawer } from "@/src/components/admin/Drawer";
import { Column, Table } from "@/src/components/admin/Table";
import { fonts } from "@/src/hooks/use-app-fonts";
import { space, useTheme } from "@/src/theme";
import { Btn } from "@/src/components/ui";

type Dispute = {
  id: string; order_id: string; reason: string; description?: string; status: string;
  reporter_name?: string; created_at: string;
};

const STATUS_OPTIONS = [
  { value: "OPEN", label: "Aberta" }, { value: "UNDER_REVIEW", label: "Em análise" },
  { value: "WAITING_CUSTOMER", label: "Aguardando cliente" }, { value: "WAITING_PROVIDER", label: "Aguardando fazedor" },
  { value: "RESOLVED", label: "Resolvida" }, { value: "REJECTED", label: "Rejeitada" }, { value: "CANCELLED", label: "Cancelada" },
];
const TONE: Record<string, BadgeTone> = { OPEN: "amber", UNDER_REVIEW: "amber", WAITING_CUSTOMER: "amber", WAITING_PROVIDER: "amber", RESOLVED: "green", REJECTED: "neutral", CANCELLED: "neutral" };
const OPEN_STATES = ["OPEN", "UNDER_REVIEW", "WAITING_CUSTOMER", "WAITING_PROVIDER"];

export default function AdminDisputes() {
  const { colors } = useTheme();
  const { admin } = useAdminAuth();
  const canResolve = hasPermission(admin, "disputes.resolve");
  const [status, setStatus] = useState<string | null>(null);
  const [items, setItems] = useState<Dispute[]>([]);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<Dispute | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    const params = status ? `?status=${status}` : "";
    adminApi.get(`/admin/disputes${params}`).then(setItems).catch(() => {}).finally(() => setLoading(false));
  }, [status]);

  useEffect(() => { load(); }, [load]);

  const act = async (body: object) => {
    if (!detail) return;
    setBusy(true);
    try {
      await adminApi.patch(`/admin/disputes/${detail.id}`, body);
      setDetail(null);
      load();
    } catch (e: any) {
      Alert.alert("Ops", e.message || "Não foi possível concluir.");
    } finally {
      setBusy(false);
    }
  };

  const columns: Column<Dispute>[] = [
    { key: "reason", label: "Motivo", width: 2, render: (d) => (
      <View>
        <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 13 }} numberOfLines={1}>{d.reason}</Text>
        <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 11 }}>Por {d.reporter_name || "—"} · pedido {d.order_id.slice(0, 8)}</Text>
      </View>
    ) },
    { key: "status", label: "Status", render: (d) => <Badge label={STATUS_OPTIONS.find((s) => s.value === d.status)?.label || d.status} tone={TONE[d.status] || "neutral"} /> },
    { key: "created_at", label: "Aberta em", render: (d) => <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 12 }}>{new Date(d.created_at).toLocaleString("pt-BR")}</Text> },
  ];

  return (
    <View style={{ gap: space.lg }}>
      <View style={{ width: 240 }}>
        <AdminSelect label="Status" value={status} options={STATUS_OPTIONS} onChange={setStatus} testID="admin-disputes-status-filter" />
      </View>

      <Table columns={columns} rows={items} loading={loading} emptyIcon="warning-outline" emptyLabel="Nenhuma disputa encontrada." onRowPress={setDetail} />

      <Drawer visible={!!detail} onClose={() => setDetail(null)} title="Disputa">
        {detail && (
          <>
            <Badge label={STATUS_OPTIONS.find((s) => s.value === detail.status)?.label || detail.status} tone={TONE[detail.status] || "neutral"} />
            <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 15 }}>{detail.reason}</Text>
            {detail.description ? <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 14, lineHeight: 20 }}>{detail.description}</Text> : null}
            <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 12 }}>Por {detail.reporter_name} · pedido {detail.order_id}</Text>

            {OPEN_STATES.includes(detail.status) && (
              canResolve ? (
                <View style={{ gap: space.sm }}>
                  <View style={{ flexDirection: "row", gap: space.sm }}>
                    <View style={{ flex: 1 }}><Btn small title="Reembolsar cliente" disabled={busy} onPress={() => act({ status: "RESOLVED", resolution: "Reembolso concedido", resolution_action: "refund_client" })} /></View>
                    <View style={{ flex: 1 }}><Btn small variant="secondary" title="Liberar p/ fazedor" disabled={busy} onPress={() => act({ status: "RESOLVED", resolution: "Liberado para o fazedor", resolution_action: "release_worker" })} /></View>
                  </View>
                  <Btn small variant="danger" title="Rejeitar disputa" disabled={busy} onPress={() => act({ status: "REJECTED", resolution: "Disputa rejeitada", resolution_action: "none" })} />
                  <View style={{ flexDirection: "row", gap: space.sm }}>
                    <View style={{ flex: 1 }}><Btn small variant="ghost" title="Aguardando cliente" disabled={busy} onPress={() => act({ status: "WAITING_CUSTOMER", resolution: "", resolution_action: "none" })} /></View>
                    <View style={{ flex: 1 }}><Btn small variant="ghost" title="Aguardando fazedor" disabled={busy} onPress={() => act({ status: "WAITING_PROVIDER", resolution: "", resolution_action: "none" })} /></View>
                  </View>
                </View>
              ) : (
                // Resolving a dispute always touches money (refund/release), so the
                // backend gates the whole PATCH behind disputes.resolve (OWNER/MANAGER only) —
                // SUPPORT can review and escalate, but not act here.
                <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 12 }}>Resolução disponível apenas para o administrador principal. Encaminhe para análise.</Text>
              )
            )}
          </>
        )}
      </Drawer>
    </View>
  );
}
