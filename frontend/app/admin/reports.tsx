import React, { useCallback, useEffect, useState } from "react";
import { Alert, Text, View } from "react-native";

import { adminApi } from "@/src/admin-api";
import { AdminSelect } from "@/src/components/admin/AdminSelect";
import { Badge, BadgeTone } from "@/src/components/admin/Badge";
import { Drawer } from "@/src/components/admin/Drawer";
import { Column, Table } from "@/src/components/admin/Table";
import { fonts } from "@/src/hooks/use-app-fonts";
import { space, useTheme } from "@/src/theme";
import { Btn } from "@/src/components/ui";

type Report = {
  id: string; target_type: string; target_id: string; reason: string; details?: string;
  status: string; reporter_name?: string; created_at: string;
};

const STATUS_OPTIONS = [
  { value: "OPEN", label: "Aberta" }, { value: "UNDER_REVIEW", label: "Em análise" },
  { value: "RESOLVED", label: "Resolvida" }, { value: "REJECTED", label: "Rejeitada" },
];
const TONE: Record<string, BadgeTone> = { OPEN: "amber", UNDER_REVIEW: "amber", RESOLVED: "green", REJECTED: "neutral" };

export default function AdminReports() {
  const { colors } = useTheme();
  const [items, setItems] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<Report | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    adminApi.get("/admin/reports").then(setItems).catch(() => {}).finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const act = async (status: string) => {
    if (!detail) return;
    setBusy(true);
    try {
      await adminApi.patch(`/admin/reports/${detail.id}`, { status, resolution: "" });
      setDetail(null);
      load();
    } catch (e: any) {
      Alert.alert("Ops", e.message || "Não foi possível concluir.");
    } finally {
      setBusy(false);
    }
  };

  const columns: Column<Report>[] = [
    { key: "reason", label: "Denúncia", width: 2, render: (r) => (
      <View>
        <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 13 }} numberOfLines={1}>{r.reason}</Text>
        <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 11 }}>Por {r.reporter_name || "—"} · alvo: {r.target_type}</Text>
      </View>
    ) },
    { key: "status", label: "Status", render: (r) => <Badge label={STATUS_OPTIONS.find((s) => s.value === r.status)?.label || r.status} tone={TONE[r.status] || "neutral"} /> },
    { key: "created_at", label: "Aberta em", render: (r) => <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 12 }}>{new Date(r.created_at).toLocaleString("pt-BR")}</Text> },
  ];

  return (
    <View style={{ gap: space.lg }}>
      <Table columns={columns} rows={items} loading={loading} emptyIcon="flag-outline" emptyLabel="Nenhuma denúncia registrada." onRowPress={setDetail} />

      <Drawer visible={!!detail} onClose={() => setDetail(null)} title="Denúncia">
        {detail && (
          <>
            <Badge label={STATUS_OPTIONS.find((s) => s.value === detail.status)?.label || detail.status} tone={TONE[detail.status] || "neutral"} />
            <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 15 }}>{detail.reason}</Text>
            {detail.details ? <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 14, lineHeight: 20 }}>{detail.details}</Text> : null}
            <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 12 }}>Por {detail.reporter_name} · alvo: {detail.target_type} ({detail.target_id})</Text>
            {["OPEN", "UNDER_REVIEW"].includes(detail.status) && (
              <View style={{ flexDirection: "row", gap: space.sm }}>
                <View style={{ flex: 1 }}><Btn small title="Marcar em análise" disabled={busy} onPress={() => act("UNDER_REVIEW")} /></View>
                <View style={{ flex: 1 }}><Btn small title="Resolver" disabled={busy} onPress={() => act("RESOLVED")} /></View>
                <View style={{ flex: 1 }}><Btn small variant="secondary" title="Rejeitar" disabled={busy} onPress={() => act("REJECTED")} /></View>
              </View>
            )}
          </>
        )}
      </Drawer>
    </View>
  );
}
