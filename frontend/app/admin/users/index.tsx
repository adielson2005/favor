import { Ionicons } from "@expo/vector-icons";
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
import { Btn, Field } from "@/src/components/ui";

type AdminUser = {
  id: string; name: string; email?: string; phone?: string | null; city_id?: string;
  account_status?: string; verified_email?: boolean; verified_phone?: boolean; verified_identity?: boolean;
  blocked?: boolean; is_admin?: boolean; member_since?: string; created_at: string; rating?: number; jobs_done?: number;
};

const STATUS_OPTIONS = [
  { value: "ACTIVE", label: "Ativo" },
  { value: "PENDING_VERIFICATION", label: "Verificação pendente" },
  { value: "SUSPENDED", label: "Suspenso" },
  { value: "BLOCKED", label: "Bloqueado" },
];

const STATUS_TONE: Record<string, BadgeTone> = {
  ACTIVE: "green", PENDING_VERIFICATION: "amber", SUSPENDED: "danger", BLOCKED: "danger",
};

const PAGE_SIZE = 25;

export default function AdminUsers() {
  const { colors } = useTheme();
  const { admin } = useAdminAuth();

  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [items, setItems] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(page * PAGE_SIZE) });
    if (search.trim()) params.set("search", search.trim());
    if (status) params.set("status", status);
    adminApi.get(`/admin/users?${params.toString()}`)
      .then((d) => { setItems(d.items); setTotal(d.total); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [search, status, page]);

  useEffect(() => { load(); }, [load]);

  const [detailId, setDetailId] = useState<string | null>(null);

  const columns: Column<AdminUser>[] = [
    { key: "name", label: "Nome", width: 2, render: (u) => (
      <View>
        <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 13 }} numberOfLines={1}>{u.name}{u.is_admin ? " · admin" : ""}</Text>
        <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 11 }} numberOfLines={1}>{u.email || u.phone || "—"}</Text>
      </View>
    ) },
    { key: "account_status", label: "Status", render: (u) => <Badge label={u.account_status || "—"} tone={STATUS_TONE[u.account_status || ""] || "neutral"} /> },
    { key: "verified", label: "Verificado", render: (u) => (
      <View style={{ flexDirection: "row", gap: 6 }}>
        <Ionicons name="mail" size={14} color={u.verified_email ? colors.green : colors.faint} />
        <Ionicons name="call" size={14} color={u.verified_phone ? colors.green : colors.faint} />
        <Ionicons name="shield-checkmark" size={14} color={u.verified_identity ? colors.green : colors.faint} />
      </View>
    ) },
    { key: "blocked", label: "Bloqueado", render: (u) => u.blocked ? <Badge label="Bloqueado" tone="danger" /> : <Text style={{ color: colors.faint, fontSize: 12 }}>—</Text> },
    { key: "created_at", label: "Cadastro", render: (u) => <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 12 }}>{new Date(u.created_at).toLocaleDateString("pt-BR")}</Text> },
  ];

  return (
    <View style={{ gap: space.lg }}>
      <View style={{ flexDirection: "row", gap: space.md, flexWrap: "wrap", alignItems: "flex-end" }}>
        <View style={{ minWidth: 260, flex: 1 }}>
          <Field label="Buscar" placeholder="Nome, e-mail, telefone ou ID" value={search} onChangeText={setSearch} onSubmitEditing={() => { setPage(0); load(); }} testID="admin-users-search" />
        </View>
        <View style={{ width: 220 }}>
          <AdminSelect label="Status" value={status} options={STATUS_OPTIONS} onChange={(v) => { setStatus(v); setPage(0); }} testID="admin-users-status-filter" />
        </View>
        <Btn title="Buscar" small onPress={() => { setPage(0); load(); }} />
      </View>

      <Table
        columns={columns}
        rows={items}
        loading={loading}
        emptyIcon="people-outline"
        emptyLabel="Nenhum usuário encontrado."
        onRowPress={(u) => setDetailId(u.id)}
        page={page}
        pageSize={PAGE_SIZE}
        total={total}
        onPageChange={setPage}
      />

      <UserDetailDrawer userId={detailId} onClose={() => setDetailId(null)} onChanged={load} canManageStatus={hasPermission(admin, "users.status.manage")} />
    </View>
  );
}

function UserDetailDrawer({ userId, onClose, onChanged, canManageStatus }: { userId: string | null; onClose: () => void; onChanged: () => void; canManageStatus: boolean }) {
  const { colors } = useTheme();
  const [data, setData] = useState<{ user: AdminUser; orders: any[]; payments: any[]; disputes: any[]; reports: any[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmRevoke, setConfirmRevoke] = useState(false);

  useEffect(() => {
    if (!userId) { setData(null); return; }
    adminApi.get(`/admin/users/${userId}`).then(setData).catch(() => {});
  }, [userId]);

  const act = async (fn: () => Promise<any>) => {
    setBusy(true);
    try {
      await fn();
      const fresh = await adminApi.get(`/admin/users/${userId}`);
      setData(fresh);
      onChanged();
    } catch (e: any) {
      Alert.alert("Ops", e.message || "Não foi possível concluir.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer visible={!!userId} onClose={onClose} title={data?.user.name || "Usuário"}>
      {data && (
        <>
          <View style={{ gap: 4 }}>
            <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 13 }}>{data.user.email || "sem e-mail"}</Text>
            <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 13 }}>{data.user.phone || "sem telefone"}</Text>
            <View style={{ flexDirection: "row", gap: 6, marginTop: 6 }}>
              <Badge label={data.user.account_status || "—"} tone={STATUS_TONE[data.user.account_status || ""] || "neutral"} />
              {data.user.blocked && <Badge label="Bloqueado" tone="danger" />}
            </View>
          </View>

          <View style={{ gap: space.sm }}>
            <View style={{ flexDirection: "row", gap: space.sm }}>
              <View style={{ flex: 1 }}>
                <Btn small variant={data.user.blocked ? "secondary" : "danger"} title={data.user.blocked ? "Desbloquear" : "Bloquear"}
                     disabled={busy} onPress={() => act(() => adminApi.post(`/admin/users/${userId}/block`))} testID="user-drawer-toggle-block" />
              </View>
              <View style={{ flex: 1 }}>
                <Btn small variant="secondary" title={data.user.verified_identity ? "Remover selo" : "Verificar identidade"}
                     disabled={busy} onPress={() => act(() => adminApi.post(`/admin/users/${userId}/verify`))} />
              </View>
            </View>
            <Btn small variant="ghost" title="Encerrar sessões" disabled={busy} onPress={() => setConfirmRevoke(true)} />
            {canManageStatus && (
              <View style={{ flexDirection: "row", gap: space.sm, flexWrap: "wrap" }}>
                {STATUS_OPTIONS.map((s) => (
                  <View key={s.value} style={{ minWidth: 130, flexGrow: 1 }}>
                    <Btn small variant={data.user.account_status === s.value ? "primary" : "secondary"} title={s.label} disabled={busy}
                         onPress={() => act(() => adminApi.patch(`/admin/users/${userId}/status`, { status: s.value }))} />
                  </View>
                ))}
              </View>
            )}
          </View>

          <Section title={`Pedidos (${data.orders.length})`}>
            {data.orders.slice(0, 10).map((o) => (
              <Row key={o.id} label={o.title} value={o.status} />
            ))}
            {data.orders.length === 0 && <Empty />}
          </Section>

          <Section title={`Pagamentos (${data.payments.length})`}>
            {data.payments.slice(0, 10).map((p) => (
              <Row key={p.id} label={`R$ ${p.gross_amount?.toFixed(2)}`} value={p.status} />
            ))}
            {data.payments.length === 0 && <Empty />}
          </Section>

          <Section title={`Disputas (${data.disputes.length})`}>
            {data.disputes.slice(0, 10).map((d) => (
              <Row key={d.id} label={d.reason} value={d.status} />
            ))}
            {data.disputes.length === 0 && <Empty />}
          </Section>

          <Section title={`Denúncias (${data.reports.length})`}>
            {data.reports.slice(0, 10).map((r) => (
              <Row key={r.id} label={r.reason} value={r.status} />
            ))}
            {data.reports.length === 0 && <Empty />}
          </Section>
        </>
      )}

      <ConfirmDialog
        visible={confirmRevoke}
        onClose={() => setConfirmRevoke(false)}
        onConfirm={() => { setConfirmRevoke(false); act(() => adminApi.post(`/admin/users/${userId}/revoke-sessions`)); }}
        title="Encerrar sessões"
        message="Este usuário vai precisar entrar novamente em todos os dispositivos. Continuar?"
        confirmLabel="Encerrar"
        danger
      />
    </Drawer>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  const { colors } = useTheme();
  return (
    <View style={{ gap: space.sm }}>
      <Text style={{ color: colors.faint, fontFamily: fonts.bodyBold, fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5 }}>{title}</Text>
      <View style={{ gap: 6 }}>{children}</View>
    </View>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", justifyContent: "space-between", gap: space.sm, paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: colors.border }}>
      <Text style={{ color: colors.ink, fontFamily: fonts.body, fontSize: 13, flex: 1 }} numberOfLines={1}>{label}</Text>
      <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 12 }}>{value}</Text>
    </View>
  );
}

function Empty() {
  const { colors } = useTheme();
  return <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 12 }}>Nenhum registro.</Text>;
}
