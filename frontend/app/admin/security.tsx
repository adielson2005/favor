import React, { useCallback, useEffect, useState } from "react";
import { Alert, Pressable, Text, View } from "react-native";

import { adminApi, hasPermission } from "@/src/admin-api";
import { useAdminAuth } from "@/src/admin-auth";
import { AdminSelect } from "@/src/components/admin/AdminSelect";
import { Badge, BadgeTone } from "@/src/components/admin/Badge";
import { Drawer } from "@/src/components/admin/Drawer";
import { Column, Table } from "@/src/components/admin/Table";
import { fonts } from "@/src/hooks/use-app-fonts";
import { space, useTheme } from "@/src/theme";
import { Btn } from "@/src/components/ui";

type RiskFlag = {
  id: string; user_id: string; user_name?: string; kind: string; reference_id: string;
  level: string; reasons: string[]; status: string; note?: string; created_at: string;
};
type SecurityEvent = { id: string; user_id: string; event: string; detail?: string; ip?: string; created_at: string };

const LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"] as const;
const LEVEL_TONE: Record<string, BadgeTone> = { LOW: "neutral", MEDIUM: "amber", HIGH: "danger", CRITICAL: "danger" };
const STATUS_OPTIONS = [{ value: "OPEN", label: "Aberta" }, { value: "RESOLVED", label: "Resolvida" }, { value: "DISMISSED", label: "Descartada" }];
const STATUS_TONE: Record<string, BadgeTone> = { OPEN: "amber", RESOLVED: "green", DISMISSED: "neutral" };

export default function AdminSecurity() {
  const { colors } = useTheme();
  const { admin } = useAdminAuth();
  const canManage = hasPermission(admin, "risk.manage");

  const [status, setStatus] = useState<string | null>("OPEN");
  const [level, setLevel] = useState<string | null>(null);
  const [items, setItems] = useState<RiskFlag[]>([]);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<RiskFlag | null>(null);
  const [busy, setBusy] = useState(false);
  const [events, setEvents] = useState<SecurityEvent[]>([]);

  const load = useCallback(() => {
    setLoading(true);
    const params = status ? `?status=${status}` : "";
    adminApi.get(`/admin/risk-flags${params}`).then(setItems).catch(() => {}).finally(() => setLoading(false));
  }, [status]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (hasPermission(admin, "security_events.view")) {
      adminApi.get("/admin/security-events?limit=50").then(setEvents).catch(() => {});
    }
  }, [admin]);

  const act = async (flagStatus: string) => {
    if (!detail) return;
    setBusy(true);
    try {
      await adminApi.patch(`/admin/risk-flags/${detail.id}`, { status: flagStatus, note: "" });
      setDetail(null);
      load();
    } catch (e: any) {
      Alert.alert("Ops", e.message || "Não foi possível concluir.");
    } finally {
      setBusy(false);
    }
  };

  const filtered = level ? items.filter((f) => f.level === level) : items;
  const counts = LEVELS.reduce((acc, l) => ({ ...acc, [l]: items.filter((f) => f.level === l).length }), {} as Record<string, number>);

  const columns: Column<RiskFlag>[] = [
    { key: "user_name", label: "Usuário", render: (f) => (
      <View>
        <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 13 }}>{f.user_name || "—"}</Text>
        <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 11 }}>{f.kind}</Text>
      </View>
    ) },
    { key: "level", label: "Nível", render: (f) => <Badge label={f.level} tone={LEVEL_TONE[f.level] || "neutral"} /> },
    { key: "status", label: "Status", render: (f) => <Badge label={STATUS_OPTIONS.find((s) => s.value === f.status)?.label || f.status} tone={STATUS_TONE[f.status] || "neutral"} /> },
    { key: "created_at", label: "Detectada em", render: (f) => <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 12 }}>{new Date(f.created_at).toLocaleString("pt-BR")}</Text> },
  ];

  const eventColumns: Column<SecurityEvent>[] = [
    { key: "event", label: "Evento", render: (e) => <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 13 }}>{e.event}</Text> },
    { key: "detail", label: "Detalhe", width: 2, render: (e) => <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 12 }} numberOfLines={1}>{e.detail || "—"}</Text> },
    { key: "ip", label: "IP", render: (e) => <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 12 }}>{e.ip || "—"}</Text> },
    { key: "created_at", label: "Quando", render: (e) => <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 12 }}>{new Date(e.created_at).toLocaleString("pt-BR")}</Text> },
  ];

  return (
    <View style={{ gap: space.xl }}>
      <View style={{ gap: space.sm }}>
        <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 16 }}>Sinalizações de risco</Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.md }}>
          {LEVELS.map((l) => {
            const active = level === l;
            return (
              <Pressable key={l} testID={`admin-security-level-tile-${l}`} onPress={() => setLevel(active ? null : l)}>
                <Badge label={`${l} · ${counts[l] || 0}`} tone={active ? LEVEL_TONE[l] : "neutral"} />
              </Pressable>
            );
          })}
        </View>
        <View style={{ flexDirection: "row", gap: space.md, flexWrap: "wrap" }}>
          <View style={{ width: 220 }}>
            <AdminSelect label="Status" value={status} options={STATUS_OPTIONS} onChange={setStatus} testID="admin-security-status-filter" />
          </View>
          <View style={{ width: 220 }}>
            <AdminSelect
              label="Nível"
              value={level}
              options={LEVELS.map((l) => ({ value: l, label: l }))}
              onChange={setLevel}
              testID="admin-security-level-filter"
            />
          </View>
        </View>

        <Table columns={columns} rows={filtered} loading={loading} emptyIcon="shield-outline" emptyLabel="Nenhuma sinalização encontrada." onRowPress={setDetail} />
      </View>

      {hasPermission(admin, "security_events.view") && (
        <View style={{ gap: space.sm }}>
          <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 16 }}>Eventos de segurança recentes</Text>
          <Table columns={eventColumns} rows={events} emptyIcon="lock-closed-outline" emptyLabel="Nenhum evento registrado ainda." />
        </View>
      )}

      <Drawer visible={!!detail} onClose={() => setDetail(null)} title="Sinalização de risco">
        {detail && (
          <>
            <View style={{ flexDirection: "row", gap: space.sm }}>
              <Badge label={detail.level} tone={LEVEL_TONE[detail.level] || "neutral"} />
              <Badge label={STATUS_OPTIONS.find((s) => s.value === detail.status)?.label || detail.status} tone={STATUS_TONE[detail.status] || "neutral"} />
            </View>
            <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 15 }}>{detail.kind}</Text>
            <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 12 }}>Usuário: {detail.user_name} · ref: {detail.reference_id}</Text>
            <View style={{ gap: 6 }}>
              {detail.reasons.map((r, i) => (
                <View key={i} style={{ flexDirection: "row", gap: 8, alignItems: "flex-start" }}>
                  <View style={{ width: 5, height: 5, borderRadius: 3, backgroundColor: colors.muted, marginTop: 7 }} />
                  <Text style={{ flex: 1, color: colors.muted, fontFamily: fonts.body, fontSize: 13, lineHeight: 19 }}>{r}</Text>
                </View>
              ))}
            </View>

            {detail.status === "OPEN" && (
              canManage ? (
                <View style={{ flexDirection: "row", gap: space.sm }}>
                  <View style={{ flex: 1 }}><Btn small title="Resolver" disabled={busy} onPress={() => act("RESOLVED")} /></View>
                  <View style={{ flex: 1 }}><Btn small variant="secondary" title="Descartar" disabled={busy} onPress={() => act("DISMISSED")} /></View>
                </View>
              ) : (
                <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 12 }}>Resolver sinalizações é uma ação restrita ao administrador principal.</Text>
              )
            )}
          </>
        )}
      </Drawer>
    </View>
  );
}
