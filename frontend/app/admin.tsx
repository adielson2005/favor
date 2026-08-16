import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useCallback, useEffect, useState } from "react";
import { Alert, Pressable, ScrollView, Switch, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Btn, Chip } from "@/src/components/ui";
import { useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

type Section = "overview" | "users" | "orders" | "categories" | "geo" | "reports" | "audit";
const SECTIONS: { key: Section; label: string }[] = [
  { key: "overview", label: "Visão geral" }, { key: "users", label: "Usuários" },
  { key: "orders", label: "Pedidos" }, { key: "categories", label: "Categorias" },
  { key: "geo", label: "Localidades" }, { key: "reports", label: "Denúncias" },
  { key: "audit", label: "Auditoria" },
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
    categories: "/admin/categories", geo: "/admin/geo", reports: "/admin/reports", audit: "/admin/audit",
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
            {[["Usuários", data.users], ["Pedidos", data.orders], ["Pedidos abertos", data.orders_open], ["Propostas", data.proposals], ["Avaliações", data.reviews], ["Denúncias abertas", data.reports_open], ["Categorias", data.categories], ["Bairros", data.neighborhoods]].map(([label, value]) => (
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
              <Text style={{ color: report.status === "open" ? colors.amber : colors.green, fontSize: 12, fontWeight: "700" }}>{report.status === "open" ? "Aberta" : "Resolvida"}</Text>
            </View>
            {report.details ? <Text style={{ color: colors.muted, fontSize: 13 }}>{report.details}</Text> : null}
            <Text style={{ color: colors.faint, fontSize: 12 }}>Por {report.reporter_name} · alvo: {report.target_type}</Text>
            {report.status === "open" && <Btn small variant="secondary" title="Marcar como resolvida" onPress={() => act(() => api.post(`/admin/reports/${report.id}/resolve`))} />}
          </View>
        )))}

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
