import React, { useCallback, useEffect, useState } from "react";
import { Alert, Text, View } from "react-native";

import { adminApi, hasPermission } from "@/src/admin-api";
import { useAdminAuth } from "@/src/admin-auth";
import { AdminSelect } from "@/src/components/admin/AdminSelect";
import { Badge, BadgeTone } from "@/src/components/admin/Badge";
import { ConfirmDialog } from "@/src/components/admin/Dialog";
import { Drawer } from "@/src/components/admin/Drawer";
import { Column, Table } from "@/src/components/admin/Table";
import { fonts } from "@/src/hooks/use-app-fonts";
import { space, useTheme } from "@/src/theme";
import { Btn, Chip } from "@/src/components/ui";

type AdminOrder = {
  id: string; title: string; status: string; budget: number; urgent?: boolean;
  client_id: string; worker_id?: string | null; city_id?: string; created_at: string; description?: string;
};

const STATUS_OPTIONS = [
  { value: "published", label: "Publicado" },
  { value: "accepted", label: "Aceito" },
  { value: "in_progress", label: "Em andamento" },
  { value: "completion_requested", label: "Conclusão solicitada" },
  { value: "completed", label: "Concluído" },
  { value: "cancelled", label: "Cancelado" },
  { value: "disputed", label: "Disputado" },
];

const STATUS_TONE: Record<string, BadgeTone> = {
  published: "primary", accepted: "amber", in_progress: "amber", completion_requested: "amber",
  completed: "green", cancelled: "neutral", disputed: "danger",
};

const CANCELLABLE = ["published", "accepted", "in_progress", "completion_requested"];

export default function AdminOrders() {
  const { colors } = useTheme();
  const { admin } = useAdminAuth();
  const [status, setStatus] = useState<string | null>(null);
  const [urgentOnly, setUrgentOnly] = useState(false);
  const [items, setItems] = useState<AdminOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<AdminOrder | null>(null);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (urgentOnly) params.set("urgent", "true");
    adminApi.get(`/admin/orders?${params.toString()}`).then(setItems).catch(() => {}).finally(() => setLoading(false));
  }, [status, urgentOnly]);

  useEffect(() => { load(); }, [load]);

  const cancelOrder = async () => {
    if (!detail) return;
    setBusy(true);
    try {
      await adminApi.post(`/admin/orders/${detail.id}/cancel`);
      setConfirmCancel(false);
      setDetail(null);
      load();
    } catch (e: any) {
      Alert.alert("Ops", e.message || "Não foi possível cancelar.");
    } finally {
      setBusy(false);
    }
  };

  const columns: Column<AdminOrder>[] = [
    { key: "title", label: "Pedido", width: 2, render: (o) => (
      <View>
        <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 13 }} numberOfLines={1}>{o.title}{o.urgent ? " ⚡" : ""}</Text>
        <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 11 }}>R$ {o.budget?.toFixed(2)}</Text>
      </View>
    ) },
    { key: "status", label: "Status", render: (o) => <Badge label={STATUS_OPTIONS.find((s) => s.value === o.status)?.label || o.status} tone={STATUS_TONE[o.status] || "neutral"} /> },
    { key: "created_at", label: "Criado em", render: (o) => <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 12 }}>{new Date(o.created_at).toLocaleDateString("pt-BR")}</Text> },
  ];

  return (
    <View style={{ gap: space.lg }}>
      <View style={{ flexDirection: "row", gap: space.md, flexWrap: "wrap", alignItems: "flex-end" }}>
        <View style={{ width: 240 }}>
          <AdminSelect label="Status" value={status} options={STATUS_OPTIONS} onChange={setStatus} testID="admin-orders-status-filter" />
        </View>
        <Chip label="Só urgentes" active={urgentOnly} onPress={() => setUrgentOnly((v) => !v)} testID="admin-orders-urgent-filter" />
      </View>

      <Table
        columns={columns}
        rows={items}
        loading={loading}
        emptyIcon="briefcase-outline"
        emptyLabel="Nenhum pedido encontrado."
        onRowPress={setDetail}
      />

      <Drawer visible={!!detail} onClose={() => setDetail(null)} title={detail?.title}>
        {detail && (
          <>
            <View style={{ flexDirection: "row", gap: 6 }}>
              <Badge label={STATUS_OPTIONS.find((s) => s.value === detail.status)?.label || detail.status} tone={STATUS_TONE[detail.status] || "neutral"} />
              {detail.urgent && <Badge label="Urgente" tone="amber" />}
            </View>
            <Text style={{ color: colors.ink, fontFamily: fonts.body, fontSize: 14, lineHeight: 20 }}>{detail.description || "Sem descrição."}</Text>
            <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 13 }}>Valor: R$ {detail.budget?.toFixed(2)}</Text>
            <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 12 }}>Cliente: {detail.client_id}</Text>
            {detail.worker_id && <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 12 }}>Fazedor: {detail.worker_id}</Text>}
            {hasPermission(admin, "orders.cancel") && CANCELLABLE.includes(detail.status) && (
              <>
                <Btn small variant="danger" title="Cancelar pedido" onPress={() => setConfirmCancel(true)} testID="admin-order-cancel-button" />
                <ConfirmDialog
                  visible={confirmCancel}
                  onClose={() => setConfirmCancel(false)}
                  onConfirm={cancelOrder}
                  title="Cancelar pedido"
                  message="O cliente será reembolsado automaticamente se houver pagamento retido. Continuar?"
                  confirmLabel="Cancelar pedido"
                  danger
                  loading={busy}
                />
              </>
            )}
          </>
        )}
      </Drawer>
    </View>
  );
}
