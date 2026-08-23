import React, { useCallback, useEffect, useState } from "react";
import { Alert, Text, View } from "react-native";

import { adminApi } from "@/src/admin-api";
import { AdminSelect } from "@/src/components/admin/AdminSelect";
import { Badge, BadgeTone } from "@/src/components/admin/Badge";
import { ConfirmDialog } from "@/src/components/admin/Dialog";
import { Drawer } from "@/src/components/admin/Drawer";
import { Column, Table } from "@/src/components/admin/Table";
import { fonts } from "@/src/hooks/use-app-fonts";
import { space, useTheme } from "@/src/theme";
import { Btn } from "@/src/components/ui";

type Withdrawal = {
  id: string; amount: number; status: string; risk_level?: string; reason?: string;
  bank_account_snapshot?: { holder_name?: string; account_number_masked?: string };
  created_at: string;
};

const STATUS_OPTIONS = [
  { value: "PENDING", label: "Pendente" }, { value: "REVIEW_REQUIRED", label: "Em análise" },
  { value: "COMPLETED", label: "Processado" }, { value: "FAILED", label: "Recusado" }, { value: "CANCELLED", label: "Cancelado" },
];
const TONE: Record<string, BadgeTone> = { PENDING: "amber", REVIEW_REQUIRED: "amber", COMPLETED: "green", FAILED: "danger", CANCELLED: "neutral" };
const ACTIONABLE = ["PENDING", "REVIEW_REQUIRED"];

export default function AdminWithdrawals() {
  const { colors } = useTheme();
  const [status, setStatus] = useState<string | null>(null);
  const [items, setItems] = useState<Withdrawal[]>([]);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<Withdrawal | null>(null);
  const [confirmReject, setConfirmReject] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    const params = status ? `?status=${status}` : "";
    adminApi.get(`/admin/withdrawals${params}`).then(setItems).catch(() => {}).finally(() => setLoading(false));
  }, [status]);

  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<any>) => {
    setBusy(true);
    try { await fn(); setDetail(null); setConfirmReject(false); load(); }
    catch (e: any) { Alert.alert("Ops", e.message || "Não foi possível concluir."); }
    finally { setBusy(false); }
  };

  const columns: Column<Withdrawal>[] = [
    { key: "amount", label: "Valor", render: (w) => <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 14 }}>R$ {w.amount.toFixed(2)}</Text> },
    { key: "holder", label: "Conta", render: (w) => <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 12 }}>{w.bank_account_snapshot?.holder_name} · {w.bank_account_snapshot?.account_number_masked}</Text> },
    { key: "risk_level", label: "Risco", render: (w) => <Badge label={w.risk_level || "—"} tone={w.risk_level === "CRITICAL" || w.risk_level === "HIGH" ? "danger" : "neutral"} /> },
    { key: "status", label: "Status", render: (w) => <Badge label={STATUS_OPTIONS.find((s) => s.value === w.status)?.label || w.status} tone={TONE[w.status] || "neutral"} /> },
    { key: "created_at", label: "Solicitado em", render: (w) => <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 12 }}>{new Date(w.created_at).toLocaleString("pt-BR")}</Text> },
  ];

  return (
    <View style={{ gap: space.lg }}>
      <View style={{ width: 240 }}>
        <AdminSelect label="Status" value={status} options={STATUS_OPTIONS} onChange={setStatus} testID="admin-withdrawals-status-filter" />
      </View>

      <Table columns={columns} rows={items} loading={loading} emptyIcon="cash-outline" emptyLabel="Nenhum saque encontrado." onRowPress={setDetail} />

      <Drawer visible={!!detail} onClose={() => setDetail(null)} title="Saque">
        {detail && (
          <>
            <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 22 }}>R$ {detail.amount.toFixed(2)}</Text>
            <View style={{ flexDirection: "row", gap: 6 }}>
              <Badge label={STATUS_OPTIONS.find((s) => s.value === detail.status)?.label || detail.status} tone={TONE[detail.status] || "neutral"} />
              {detail.risk_level && <Badge label={`Risco ${detail.risk_level}`} tone={detail.risk_level === "CRITICAL" || detail.risk_level === "HIGH" ? "danger" : "neutral"} />}
            </View>
            <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 13 }}>{detail.bank_account_snapshot?.holder_name} · {detail.bank_account_snapshot?.account_number_masked}</Text>
            {detail.reason && <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 12 }}>Motivo: {detail.reason}</Text>}
            {ACTIONABLE.includes(detail.status) && (
              <View style={{ flexDirection: "row", gap: space.sm }}>
                <View style={{ flex: 1 }}>
                  <Btn title="Aprovar" disabled={busy} onPress={() => act(() => adminApi.post(`/admin/withdrawals/${detail.id}/approve`))} testID="admin-withdrawal-approve" />
                </View>
                <View style={{ flex: 1 }}>
                  <Btn title="Recusar" variant="danger" disabled={busy} onPress={() => setConfirmReject(true)} testID="admin-withdrawal-reject" />
                </View>
              </View>
            )}
          </>
        )}
        <ConfirmDialog
          visible={confirmReject}
          onClose={() => setConfirmReject(false)}
          onConfirm={() => act(() => adminApi.post(`/admin/withdrawals/${detail!.id}/reject`, { reason: "Recusado pela administração" }))}
          title="Recusar saque"
          message="O valor retorna para o saldo disponível do usuário. Continuar?"
          confirmLabel="Recusar"
          danger
          loading={busy}
        />
      </Drawer>
    </View>
  );
}
