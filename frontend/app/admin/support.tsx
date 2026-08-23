import React, { useCallback, useEffect, useState } from "react";
import { Alert, Text, View } from "react-native";

import { adminApi, hasPermission } from "@/src/admin-api";
import { useAdminAuth } from "@/src/admin-auth";
import { AdminSelect } from "@/src/components/admin/AdminSelect";
import { Badge, BadgeTone } from "@/src/components/admin/Badge";
import { Drawer } from "@/src/components/admin/Drawer";
import { Column, Table } from "@/src/components/admin/Table";
import { fonts } from "@/src/hooks/use-app-fonts";
import { space, useTheme } from "@/src/theme";
import { Btn, Field } from "@/src/components/ui";

type Message = { id: string; author_type: "user" | "admin"; author_id: string; text: string; created_at: string };
type Ticket = {
  id: string; created_by: string; category: string; subject: string; description: string;
  status: string; assigned_to: string | null; messages: Message[]; created_at: string; updated_at: string;
};

const CATEGORY_LABELS: Record<string, string> = {
  BUG: "Bug", IDEIA: "Ideia", SUGESTAO: "Sugestão", RECLAMACAO: "Reclamação",
  PAGAMENTO: "Pagamento", CONTA: "Conta", SEGURANCA: "Segurança", OUTRO: "Outro",
};
const STATUS_LABELS: Record<string, string> = {
  OPEN: "Aberto", IN_PROGRESS: "Em andamento", WAITING_USER: "Aguardando usuário", RESOLVED: "Resolvido", CLOSED: "Fechado",
};
const STATUS_TONE: Record<string, BadgeTone> = {
  OPEN: "amber", IN_PROGRESS: "amber", WAITING_USER: "primary", RESOLVED: "green", CLOSED: "neutral",
};
const CATEGORY_OPTIONS = Object.entries(CATEGORY_LABELS).map(([value, label]) => ({ value, label }));
const STATUS_OPTIONS = Object.entries(STATUS_LABELS).map(([value, label]) => ({ value, label }));

export default function AdminSupport() {
  const { colors } = useTheme();
  const { admin } = useAdminAuth();
  const canManage = hasPermission(admin, "support.manage") || hasPermission(admin, "maintenance.manage");
  const isMaintenanceOnly = !hasPermission(admin, "support.view");

  const [status, setStatus] = useState<string | null>(null);
  const [category, setCategory] = useState<string | null>(isMaintenanceOnly ? "BUG" : null);
  const [items, setItems] = useState<Ticket[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<Ticket | null>(null);
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const pageSize = 50;

  const load = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (category) params.set("category", category);
    params.set("limit", String(pageSize));
    params.set("offset", String(page * pageSize));
    adminApi.get(`/admin/tickets?${params.toString()}`)
      .then((r) => { setItems(r.items); setTotal(r.total); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [status, category, page]);

  useEffect(() => { load(); }, [load]);

  const openDetail = async (row: Ticket) => {
    try {
      const fresh = await adminApi.get(`/admin/tickets/${row.id}`);
      setDetail(fresh);
      setReply("");
    } catch (e: any) {
      Alert.alert("Ops", e.message || "Não foi possível abrir o chamado.");
    }
  };

  const sendReply = async () => {
    if (!detail || !reply.trim()) return;
    setBusy(true);
    try {
      await adminApi.post(`/admin/tickets/${detail.id}/messages`, { text: reply.trim() });
      const fresh = await adminApi.get(`/admin/tickets/${detail.id}`);
      setDetail(fresh);
      setReply("");
      load();
    } catch (e: any) {
      Alert.alert("Ops", e.message || "Não foi possível enviar a resposta.");
    } finally {
      setBusy(false);
    }
  };

  const patch = async (body: object) => {
    if (!detail) return;
    setBusy(true);
    try {
      await adminApi.patch(`/admin/tickets/${detail.id}`, body);
      const fresh = await adminApi.get(`/admin/tickets/${detail.id}`);
      setDetail(fresh);
      load();
    } catch (e: any) {
      Alert.alert("Ops", e.message || "Não foi possível concluir.");
    } finally {
      setBusy(false);
    }
  };

  const columns: Column<Ticket>[] = [
    { key: "subject", label: "Assunto", width: 2, render: (t) => (
      <View>
        <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 13 }} numberOfLines={1}>{t.subject}</Text>
        <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 11 }}>{t.messages.length} {t.messages.length === 1 ? "mensagem" : "mensagens"}</Text>
      </View>
    ) },
    { key: "category", label: "Categoria", render: (t) => <Badge label={CATEGORY_LABELS[t.category] || t.category} tone={t.category === "BUG" ? "danger" : "neutral"} /> },
    { key: "status", label: "Status", render: (t) => <Badge label={STATUS_LABELS[t.status] || t.status} tone={STATUS_TONE[t.status] || "neutral"} /> },
    { key: "created_at", label: "Aberto em", render: (t) => <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 12 }}>{new Date(t.created_at).toLocaleString("pt-BR")}</Text> },
  ];

  return (
    <View style={{ gap: space.lg }}>
      <View style={{ flexDirection: "row", gap: space.md, flexWrap: "wrap" }}>
        <View style={{ width: 220 }}>
          <AdminSelect label="Status" value={status} options={STATUS_OPTIONS} onChange={setStatus} testID="admin-tickets-status-filter" />
        </View>
        {!isMaintenanceOnly && (
          <View style={{ width: 220 }}>
            <AdminSelect label="Categoria" value={category} options={CATEGORY_OPTIONS} onChange={setCategory} testID="admin-tickets-category-filter" />
          </View>
        )}
      </View>

      <Table
        columns={columns} rows={items} loading={loading}
        emptyIcon="chatbox-ellipses-outline" emptyLabel="Nenhum chamado encontrado."
        onRowPress={openDetail} page={page} pageSize={pageSize} total={total} onPageChange={setPage}
      />

      <Drawer visible={!!detail} onClose={() => setDetail(null)} title={detail?.subject} width={480}>
        {detail && (
          <>
            <View style={{ flexDirection: "row", gap: space.sm }}>
              <Badge label={CATEGORY_LABELS[detail.category] || detail.category} tone={detail.category === "BUG" ? "danger" : "neutral"} />
              <Badge label={STATUS_LABELS[detail.status] || detail.status} tone={STATUS_TONE[detail.status] || "neutral"} />
            </View>

            <View style={{ gap: space.sm }}>
              {detail.messages.map((m) => (
                <View
                  key={m.id}
                  style={{
                    alignSelf: m.author_type === "admin" ? "flex-end" : "flex-start", maxWidth: "88%",
                    backgroundColor: m.author_type === "admin" ? colors.primarySoft : colors.alt,
                    borderRadius: 14, padding: space.md, gap: 4,
                  }}
                >
                  <Text style={{ color: colors.ink, fontFamily: fonts.body, fontSize: 14, lineHeight: 20 }}>{m.text}</Text>
                  <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 10 }}>
                    {m.author_type === "admin" ? "Equipe" : "Usuário"} · {new Date(m.created_at).toLocaleString("pt-BR")}
                  </Text>
                </View>
              ))}
            </View>

            {canManage ? (
              <>
                <Field label="Responder" value={reply} onChangeText={setReply} multiline placeholder="Escreva uma resposta ao usuário…" testID="admin-ticket-reply-input" />
                <Btn small title="Enviar resposta" disabled={busy || !reply.trim()} onPress={sendReply} testID="admin-ticket-reply-send" />

                <View style={{ flexDirection: "row", gap: space.sm, flexWrap: "wrap" }}>
                  <View style={{ flex: 1, minWidth: 140 }}><Btn small variant="secondary" title="Em andamento" disabled={busy} onPress={() => patch({ status: "IN_PROGRESS" })} /></View>
                  <View style={{ flex: 1, minWidth: 140 }}><Btn small variant="secondary" title="Marcar resolvido" disabled={busy} onPress={() => patch({ status: "RESOLVED" })} /></View>
                  <View style={{ flex: 1, minWidth: 140 }}><Btn small variant="ghost" title="Fechar chamado" disabled={busy} onPress={() => patch({ status: "CLOSED" })} /></View>
                </View>

                {detail.category !== "BUG" && !isMaintenanceOnly && (
                  <Btn small variant="danger" title="Transferir para manutenção" disabled={busy} onPress={() => patch({ transfer_to_maintenance: true })} />
                )}
              </>
            ) : (
              <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 12 }}>Você tem apenas visualização deste chamado.</Text>
            )}
          </>
        )}
      </Drawer>
    </View>
  );
}
