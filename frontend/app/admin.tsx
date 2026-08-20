import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useCallback, useEffect, useState } from "react";
import { Alert, Pressable, ScrollView, Switch, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Btn, Chip, Field } from "@/src/components/ui";
import { space, useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

type Section = "overview" | "users" | "orders" | "categories" | "geo" | "reports" | "withdrawals" | "disputes" | "risk" | "payments" | "config" | "audit";
const SECTIONS: { key: Section; label: string }[] = [
  { key: "overview", label: "Visão geral" }, { key: "users", label: "Usuários" },
  { key: "orders", label: "Pedidos" }, { key: "categories", label: "Categorias" },
  { key: "geo", label: "Localidades" }, { key: "reports", label: "Denúncias" },
  { key: "withdrawals", label: "Saques" }, { key: "disputes", label: "Disputas" },
  { key: "risk", label: "Risco" },
  { key: "payments", label: "Pagamentos" },
  { key: "config", label: "Comissão" }, { key: "audit", label: "Auditoria" },
];
const HOOD_KINDS = ["bairro", "complexo", "regiao", "distrito", "localidade"];

export default function Admin() {
  const { colors } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user } = useAuth();
  const [section, setSection] = useState<Section>("overview");
  const [payload, setPayload] = useState<{ sec: Section; value: any } | null>(null);

  const ENDPOINTS: Record<Section, string> = {
    overview: "/admin/overview", users: "/admin/users", orders: "/admin/orders",
    categories: "/admin/categories", geo: "/admin/geo", reports: "/admin/reports",
    withdrawals: "/admin/withdrawals", disputes: "/admin/disputes", risk: "/admin/risk-flags", payments: "/admin/payments",
    config: "/admin/config", audit: "/admin/audit",
  };

  const load = useCallback(async () => {
    try {
      const value = await api.get(ENDPOINTS[section]);
      setPayload({ sec: section, value });
    } catch (e: any) { Alert.alert("Ops", e.message); }
  }, [section]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!user?.is_admin) { router.replace("/(tabs)/profile"); return; }
    setPayload(null);
    load();
  }, [load, user, router]);

  const data = payload?.sec === section ? payload.value : null;

  const act = async (fn: () => Promise<any>) => {
    try { await fn(); load(); } catch (e: any) { Alert.alert("Ops", e.message); }
  };

  if (!user?.is_admin) return null;

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + 8 }}>
      <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: 20, height: 48, gap: 14 }}>
        <Pressable onPress={() => safeBack(router, "/(tabs)/profile")} hitSlop={10}><Ionicons name="arrow-back" size={24} color={colors.ink} /></Pressable>
        <Text style={{ color: colors.ink, fontSize: 18, fontWeight: "800" }}>Administração</Text>
      </View>
      <View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 20, gap: 8, paddingVertical: 10 }}>
          {SECTIONS.map((s) => <Chip key={s.key} testID={`admin-section-${s.key}`} label={s.label} active={section === s.key} onPress={() => setSection(s.key)} />)}
        </ScrollView>
      </View>
      <ScrollView contentContainerStyle={{ padding: 20, paddingBottom: 48, gap: 12 }} showsVerticalScrollIndicator={false}>
        {section === "overview" && data && (
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 10 }}>
            {[["Usuários", data.users], ["Pedidos", data.orders], ["Pedidos abertos", data.orders_open], ["Propostas", data.proposals], ["Avaliações", data.reviews], ["Denúncias abertas", data.reports_open], ["Sinalizações de risco", data.risk_flags_open], ["Categorias", data.categories], ["Bairros", data.neighborhoods]].map(([label, value]) => (
              <View key={String(label)} style={{ width: "48%", flexGrow: 1, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 16, padding: 16, gap: 4 }}>
                <Text style={{ color: colors.ink, fontSize: 24, fontWeight: "800" }}>{String(value)}</Text>
                <Text style={{ color: colors.muted, fontSize: 12 }}>{String(label)}</Text>
              </View>
            ))}
          </View>
        )}

        {section === "users" && Array.isArray(data) && data.map((user: any) => (
          <View key={user.id} style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 16, padding: 14, gap: 10 }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
              <Text style={{ color: colors.ink, fontSize: 14, fontWeight: "700", flex: 1 }}>{user.name}</Text>
              {user.blocked && <Text style={{ color: colors.danger, fontSize: 11, fontWeight: "700" }}>BLOQUEADO</Text>}
              {user.verified_identity && <Ionicons name="checkmark-circle" size={15} color={colors.green} />}
            </View>
            <Text style={{ color: colors.muted, fontSize: 12 }}>★ {user.rating} · {user.jobs_done} serviços{user.is_admin ? " · admin" : ""}</Text>
            <View style={{ flexDirection: "row", gap: 8 }}>
              <View style={{ flex: 1 }}><Btn small variant={user.blocked ? "secondary" : "danger"} title={user.blocked ? "Desbloquear" : "Bloquear"} onPress={() => act(() => api.post(`/admin/users/${user.id}/block`))} /></View>
              <View style={{ flex: 1 }}><Btn small variant="secondary" title={user.verified_identity ? "Remover selo" : "Verificar"} onPress={() => act(() => api.post(`/admin/users/${user.id}/verify`))} /></View>
            </View>
            <Btn
              small
              variant="secondary"
              title="Encerrar sessões"
              onPress={() =>
                Alert.alert("Encerrar sessões", `${user.name} vai precisar entrar novamente em todos os dispositivos. Continuar?`, [
                  { text: "Cancelar" },
                  { text: "Encerrar", style: "destructive", onPress: () => act(() => api.post(`/admin/users/${user.id}/revoke-sessions`)) },
                ])
              }
            />
            <WalletAdjust userId={user.id} act={act} />
          </View>
        ))}

        {section === "orders" && Array.isArray(data) && data.map((order: any) => (
          <View key={order.id} style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 16, padding: 14, gap: 8 }}>
            <Text style={{ color: colors.ink, fontSize: 14, fontWeight: "700" }}>{order.title}</Text>
            <Text style={{ color: colors.muted, fontSize: 12 }}>R$ {order.budget} · {order.status}</Text>
            {order.status !== "cancelled" && order.status !== "completed" && (
              <Btn small variant="danger" title="Cancelar pedido" onPress={() => act(() => api.post(`/admin/orders/${order.id}/cancel`))} />
            )}
          </View>
        ))}

        {section === "categories" && Array.isArray(data) && <Categories data={data} act={act} />}
        {section === "geo" && data && <Geo data={data} act={act} />}

        {section === "reports" && Array.isArray(data) && (data.length === 0 ? (
          <Text style={{ color: colors.muted, fontSize: 14, textAlign: "center", marginTop: 24 }}>Nenhuma denúncia registrada.</Text>
        ) : data.map((report: any) => (
          <View key={report.id} style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 16, padding: 14, gap: 8 }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <Text style={{ color: colors.ink, fontSize: 14, fontWeight: "700" }}>{report.reason}</Text>
              <Text style={{ color: report.status === "RESOLVED" ? colors.green : report.status === "REJECTED" ? colors.faint : colors.amber, fontSize: 11, fontWeight: "700" }}>{report.status}</Text>
            </View>
            {report.details ? <Text style={{ color: colors.muted, fontSize: 13 }}>{report.details}</Text> : null}
            <Text style={{ color: colors.faint, fontSize: 12 }}>Por {report.reporter_name} · alvo: {report.target_type}</Text>
            {["OPEN", "UNDER_REVIEW"].includes(report.status) && (
              <View style={{ flexDirection: "row", gap: 8 }}>
                <View style={{ flex: 1 }}><Btn small title="Resolver" onPress={() => act(() => api.patch(`/admin/reports/${report.id}`, { status: "RESOLVED", resolution: "" }))} /></View>
                <View style={{ flex: 1 }}><Btn small variant="secondary" title="Rejeitar" onPress={() => act(() => api.patch(`/admin/reports/${report.id}`, { status: "REJECTED", resolution: "" }))} /></View>
              </View>
            )}
          </View>
        )))}

        {section === "withdrawals" && Array.isArray(data) && (data.length === 0 ? (
          <Text style={{ color: colors.muted, fontSize: 14, textAlign: "center", marginTop: 24 }}>Nenhum saque solicitado.</Text>
        ) : data.map((w: any) => (
          <View key={w.id} style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 16, padding: 14, gap: 8 }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <Text style={{ color: colors.ink, fontSize: 15, fontWeight: "800" }}>R$ {w.amount.toFixed(2)}</Text>
              <Text style={{ color: w.status === "COMPLETED" ? colors.green : w.status === "FAILED" || w.status === "CANCELLED" ? colors.danger : colors.amber, fontSize: 12, fontWeight: "700" }}>{w.status}</Text>
            </View>
            <Text style={{ color: colors.muted, fontSize: 12 }}>{w.bank_account_snapshot?.holder_name} · {w.bank_account_snapshot?.account_number_masked}</Text>
            <Text style={{ color: colors.faint, fontSize: 11 }}>Risco: {w.risk_level} · {new Date(w.created_at).toLocaleString("pt-BR")}</Text>
            {["PENDING", "REVIEW_REQUIRED"].includes(w.status) && (
              <View style={{ flexDirection: "row", gap: 8 }}>
                <View style={{ flex: 1 }}><Btn small title="Aprovar" onPress={() => act(() => api.post(`/admin/withdrawals/${w.id}/approve`))} /></View>
                <View style={{ flex: 1 }}><Btn small variant="danger" title="Recusar" onPress={() => act(() => api.post(`/admin/withdrawals/${w.id}/reject`, { reason: "Recusado pela administração" }))} /></View>
              </View>
            )}
          </View>
        )))}

        {section === "disputes" && Array.isArray(data) && (data.length === 0 ? (
          <Text style={{ color: colors.muted, fontSize: 14, textAlign: "center", marginTop: 24 }}>Nenhuma disputa registrada.</Text>
        ) : data.map((d: any) => (
          <View key={d.id} style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 16, padding: 14, gap: 8 }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <Text style={{ color: colors.ink, fontSize: 14, fontWeight: "700", flex: 1 }}>{d.reason}</Text>
              <Text style={{ color: d.status === "RESOLVED" ? colors.green : ["REJECTED", "CANCELLED"].includes(d.status) ? colors.faint : colors.amber, fontSize: 11, fontWeight: "700" }}>{d.status}</Text>
            </View>
            {d.description ? <Text style={{ color: colors.muted, fontSize: 13 }}>{d.description}</Text> : null}
            <Text style={{ color: colors.faint, fontSize: 11 }}>Por {d.reporter_name} · pedido {d.order_id.slice(0, 8)}</Text>
            {["OPEN", "UNDER_REVIEW", "WAITING_CUSTOMER", "WAITING_PROVIDER"].includes(d.status) && (
              <>
                <View style={{ flexDirection: "row", gap: 8 }}>
                  <View style={{ flex: 1 }}><Btn small title="Reembolsar cliente" onPress={() => act(() => api.patch(`/admin/disputes/${d.id}`, { status: "RESOLVED", resolution: "Reembolso concedido", resolution_action: "refund_client" }))} /></View>
                  <View style={{ flex: 1 }}><Btn small variant="secondary" title="Liberar para o fazedor" onPress={() => act(() => api.patch(`/admin/disputes/${d.id}`, { status: "RESOLVED", resolution: "Liberado para o fazedor", resolution_action: "release_worker" }))} /></View>
                </View>
                <View style={{ flexDirection: "row", gap: 8 }}>
                  <View style={{ flex: 1 }}><Btn small variant="ghost" title="Aguardando cliente" onPress={() => act(() => api.patch(`/admin/disputes/${d.id}`, { status: "WAITING_CUSTOMER" }))} /></View>
                  <View style={{ flex: 1 }}><Btn small variant="ghost" title="Aguardando fazedor" onPress={() => act(() => api.patch(`/admin/disputes/${d.id}`, { status: "WAITING_PROVIDER" }))} /></View>
                </View>
                <Btn small variant="danger" title="Rejeitar disputa" onPress={() => act(() => api.patch(`/admin/disputes/${d.id}`, { status: "REJECTED", resolution: "Disputa rejeitada" }))} />
              </>
            )}
          </View>
        )))}

        {section === "risk" && Array.isArray(data) && (data.length === 0 ? (
          <Text style={{ color: colors.muted, fontSize: 14, textAlign: "center", marginTop: 24 }}>Nenhuma sinalização de risco.</Text>
        ) : data.map((f: any) => (
          <View key={f.id} style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 16, padding: 14, gap: 8 }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <Text style={{ color: colors.ink, fontSize: 14, fontWeight: "700", flex: 1 }}>{f.user_name} · {f.kind}</Text>
              <Text style={{ color: f.level === "CRITICAL" ? colors.danger : f.level === "HIGH" ? colors.amber : colors.muted, fontSize: 11, fontWeight: "700" }}>{f.level}</Text>
            </View>
            <Text style={{ color: colors.muted, fontSize: 12 }}>{(f.reasons || []).join(", ")}</Text>
            <Text style={{ color: colors.faint, fontSize: 11 }}>{f.status} · {new Date(f.created_at).toLocaleString("pt-BR")}</Text>
            {f.status === "OPEN" && (
              <View style={{ flexDirection: "row", gap: 8 }}>
                <View style={{ flex: 1 }}><Btn small title="Resolver" onPress={() => act(() => api.patch(`/admin/risk-flags/${f.id}`, { status: "RESOLVED" }))} /></View>
                <View style={{ flex: 1 }}><Btn small variant="secondary" title="Descartar" onPress={() => act(() => api.patch(`/admin/risk-flags/${f.id}`, { status: "DISMISSED" }))} /></View>
              </View>
            )}
          </View>
        )))}

        {section === "payments" && Array.isArray(data) && (data.length === 0 ? (
          <Text style={{ color: colors.muted, fontSize: 14, textAlign: "center", marginTop: 24 }}>Nenhum pagamento registrado.</Text>
        ) : data.map((p: any) => (
          <View key={p.id} style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 16, padding: 14, gap: 6 }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <Text style={{ color: colors.ink, fontSize: 15, fontWeight: "800" }}>R$ {p.gross_amount?.toFixed(2)}</Text>
              <Text style={{ color: p.status === "held" || p.status === "released" ? colors.green : p.status === "refunded" ? colors.faint : colors.amber, fontSize: 12, fontWeight: "700" }}>{p.status}</Text>
            </View>
            <Text style={{ color: colors.muted, fontSize: 12 }}>Comissão R$ {p.commission_amount?.toFixed(2)} · Líquido do prestador R$ {p.worker_net_amount?.toFixed(2)}</Text>
            <Text style={{ color: colors.faint, fontSize: 11 }}>Pedido {p.order_id?.slice(0, 8)} · {new Date(p.created_at).toLocaleString("pt-BR")}</Text>
          </View>
        )))}

        {section === "config" && data && <CommissionConfig data={data} act={act} />}

        {section === "audit" && Array.isArray(data) && (data.length === 0 ? (
          <Text style={{ color: colors.muted, fontSize: 14, textAlign: "center", marginTop: 24 }}>Nenhuma ação registrada ainda.</Text>
        ) : data.map((entry: any) => (
          <View key={entry.id} style={{ flexDirection: "row", alignItems: "center", gap: 10, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 16, padding: 14 }}>
            <View style={{ flex: 1 }}>
              <Text style={{ color: colors.ink, fontSize: 13, fontWeight: "700" }}>{entry.admin_name} · {entry.action}</Text>
              <Text style={{ color: colors.muted, fontSize: 12 }}>{entry.target}</Text>
            </View>
            <Text style={{ color: colors.faint, fontSize: 11 }}>{new Date(entry.created_at).toLocaleDateString("pt-BR")}</Text>
          </View>
        )))}
      </ScrollView>
    </View>
  );
}

function AddInline({ placeholder, onAdd }: { placeholder: string; onAdd: (name: string) => void }) {
  const { colors } = useTheme();
  const [value, setValue] = useState("");
  return (
    <View style={{ flexDirection: "row", gap: 8 }}>
      <TextInput
        value={value}
        onChangeText={setValue}
        placeholder={placeholder}
        placeholderTextColor={colors.faint}
        style={{ flex: 1, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 12, paddingHorizontal: 12, height: 42, color: colors.ink, fontSize: 13 }}
      />
      <Btn small title="Adicionar" variant="secondary" onPress={() => { if (value.trim()) { onAdd(value.trim()); setValue(""); } }} />
    </View>
  );
}

function Categories({ data, act }: { data: any[]; act: (fn: () => Promise<any>) => void }) {
  const { colors } = useTheme();
  return (
    <View style={{ gap: 12 }}>
      <AddInline placeholder="Nova categoria..." onAdd={(name) => act(() => api.post(`/admin/categories`, { name }))} />
      {data.map((cat: any) => (
        <View key={cat.id} style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 16, padding: 14, gap: 10 }}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
            <Ionicons name={cat.icon} size={17} color={colors.primary} />
            <Text style={{ color: colors.ink, fontSize: 14, fontWeight: "700", flex: 1 }}>{cat.name}</Text>
            <Switch value={cat.active} onValueChange={(v) => act(() => api.patch(`/admin/categories/${cat.id}`, { active: v }))} trackColor={{ true: colors.primary }} />
          </View>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
            {cat.subcategories.map((sub: any) => (
              <Pressable
                key={sub.id}
                onPress={() => act(() => api.patch(`/admin/subcategories/${sub.id}`, { active: !sub.active }))}
                style={{ paddingHorizontal: 10, paddingVertical: 5, borderRadius: 10, backgroundColor: sub.active ? colors.alt : "transparent", borderWidth: 1, borderColor: colors.border, opacity: sub.active ? 1 : 0.45 }}
              >
                <Text style={{ color: colors.muted, fontSize: 11, fontWeight: "600", textDecorationLine: sub.active ? "none" : "line-through" }}>{sub.name}</Text>
              </Pressable>
            ))}
          </View>
          <AddInline placeholder="Nova subcategoria..." onAdd={(name) => act(() => api.post(`/admin/subcategories`, { category_id: cat.id, name }))} />
        </View>
      ))}
    </View>
  );
}

function Geo({ data, act }: { data: { states: any[]; cities: any[]; neighborhoods: any[] }; act: (fn: () => Promise<any>) => void }) {
  const { colors } = useTheme();
  const [kind, setKind] = useState("bairro");
  const label = { color: colors.faint, fontSize: 12, fontWeight: "800" as const, textTransform: "uppercase" as const, letterSpacing: 1 };
  return (
    <View style={{ gap: 16 }}>
      <Text style={label}>Estados</Text>
      {data.states.map((state) => (
        <GeoRow key={state.id} name={`${state.name} (${state.uf})`} active={state.active} onToggle={(v) => act(() => api.patch(`/admin/geo/states/${state.id}`, { active: v }))} />
      ))}
      <Text style={label}>Cidades</Text>
      {data.cities.map((city) => (
        <GeoRow key={city.id} name={city.name} active={city.active} onToggle={(v) => act(() => api.patch(`/admin/geo/cities/${city.id}`, { active: v }))} />
      ))}
      <AddInline placeholder="Nova cidade (PA)..." onAdd={(name) => act(() => api.post(`/admin/geo/cities`, { state_id: "st-pa", name }))} />
      <Text style={label}>Bairros e regiões · Parauapebas ({data.neighborhoods.length})</Text>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
        {HOOD_KINDS.map((k) => <Chip key={k} label={k} active={kind === k} onPress={() => setKind(k)} />)}
      </View>
      <AddInline placeholder={`Novo ${kind}...`} onAdd={(name) => act(() => api.post(`/admin/geo/neighborhoods`, { city_id: "city-parauapebas", name, kind }))} />
      {data.neighborhoods.map((hood) => (
        <GeoRow key={hood.id} name={`${hood.name}${hood.kind !== "bairro" ? ` · ${hood.kind}` : ""}`} active={hood.active} onToggle={(v) => act(() => api.patch(`/admin/geo/neighborhoods/${hood.id}`, { active: v }))} />
      ))}
    </View>
  );
}

function GeoRow({ name, active, onToggle }: { name: string; active: boolean; onToggle: (v: boolean) => void }) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 10, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 8 }}>
      <Text style={{ color: colors.ink, fontSize: 13, fontWeight: "600", flex: 1 }}>{name}</Text>
      <Switch value={active} onValueChange={onToggle} trackColor={{ true: colors.primary }} />
    </View>
  );
}

function WalletAdjust({ userId, act }: { userId: string; act: (fn: () => Promise<any>) => void }) {
  const { colors } = useTheme();
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");

  if (!open) {
    return <Btn small variant="secondary" title="Ajustar saldo (teste)" onPress={() => setOpen(true)} />;
  }
  return (
    <View style={{ gap: 8, backgroundColor: colors.alt, borderRadius: 12, padding: 10 }}>
      <Text style={{ color: colors.faint, fontSize: 11 }}>Cria um ADJUSTMENT auditado — use para crédito de teste ou correção.</Text>
      <View style={{ flexDirection: "row", gap: 8 }}>
        <TextInput value={amount} onChangeText={setAmount} placeholder="Valor (+/-)" placeholderTextColor={colors.faint} keyboardType="numbers-and-punctuation"
          style={{ flex: 1, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 10, paddingHorizontal: 10, height: 38, color: colors.ink, fontSize: 12 }} />
        <TextInput value={reason} onChangeText={setReason} placeholder="Motivo" placeholderTextColor={colors.faint}
          style={{ flex: 1, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 10, paddingHorizontal: 10, height: 38, color: colors.ink, fontSize: 12 }} />
      </View>
      <View style={{ flexDirection: "row", gap: 8 }}>
        <View style={{ flex: 1 }}>
          <Btn small title="Aplicar" disabled={!Number(amount) || !reason.trim()} onPress={() => {
            act(() => api.post(`/admin/wallets/${userId}/adjust`, { user_id: userId, amount: Number(amount), reason: reason.trim() }));
            setOpen(false); setAmount(""); setReason("");
          }} />
        </View>
        <View style={{ flex: 1 }}><Btn small variant="ghost" title="Cancelar" onPress={() => setOpen(false)} /></View>
      </View>
    </View>
  );
}

function CommissionConfig({ data, act }: { data: any; act: (fn: () => Promise<any>) => void }) {
  const { colors } = useTheme();
  const [commission, setCommission] = useState(String(data.commission_percent ?? ""));
  const [minWithdrawal, setMinWithdrawal] = useState(String(data.min_withdrawal ?? ""));
  const [maxWithdrawalDay, setMaxWithdrawalDay] = useState(String(data.max_withdrawal_per_day ?? ""));
  const [maxDeposit, setMaxDeposit] = useState(String(data.max_deposit_per_transaction ?? ""));

  return (
    <View style={{ gap: space.md }}>
      <Field label="Comissão fazum (%)" value={commission} onChangeText={setCommission} keyboardType="numeric" />
      <Field label="Saque mínimo (R$)" value={minWithdrawal} onChangeText={setMinWithdrawal} keyboardType="numeric" />
      <Field label="Limite de saque por dia (R$)" value={maxWithdrawalDay} onChangeText={setMaxWithdrawalDay} keyboardType="numeric" />
      <Field label="Limite de depósito por transação (R$)" value={maxDeposit} onChangeText={setMaxDeposit} keyboardType="numeric" />
      <Btn title="Salvar configuração" onPress={() => act(() => api.patch("/admin/config", {
        commission_percent: Number(commission), min_withdrawal: Number(minWithdrawal),
        max_withdrawal_per_day: Number(maxWithdrawalDay), max_deposit_per_transaction: Number(maxDeposit),
      }))} />
    </View>
  );
}
