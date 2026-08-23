import React, { useCallback, useEffect, useState } from "react";
import { Alert, Switch, Text, View } from "react-native";

import { adminApi } from "@/src/admin-api";
import { fonts } from "@/src/hooks/use-app-fonts";
import { radius, space, useTheme } from "@/src/theme";
import { Btn, Chip, Field } from "@/src/components/ui";

type GeoState = { id: string; name: string; uf: string; active: boolean };
type City = { id: string; state_id: string; name: string; active: boolean };
type Neighborhood = { id: string; city_id: string; name: string; kind: string; active: boolean };
type Geo = { states: GeoState[]; cities: City[]; neighborhoods: Neighborhood[] };

const HOOD_KINDS = ["bairro", "complexo", "regiao", "distrito", "localidade"];

export default function AdminLocations() {
  const { colors } = useTheme();
  const [data, setData] = useState<Geo | null>(null);
  const [newCity, setNewCity] = useState("");
  const [newHood, setNewHood] = useState("");
  const [hoodKind, setHoodKind] = useState("bairro");

  const load = useCallback(() => {
    adminApi.get("/admin/geo").then(setData).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<any>) => {
    try { await fn(); load(); } catch (e: any) { Alert.alert("Ops", e.message || "Não foi possível concluir."); }
  };

  if (!data) return null;
  const label = { color: colors.faint, fontFamily: fonts.bodyBold, fontSize: 12, textTransform: "uppercase" as const, letterSpacing: 1 };

  return (
    <View style={{ gap: space.xl, maxWidth: 640 }}>
      <View style={{ gap: space.sm }}>
        <Text style={label}>Estados</Text>
        {data.states.map((s) => (
          <GeoRow key={s.id} name={`${s.name} (${s.uf})`} active={s.active} onToggle={(v) => act(() => adminApi.patch(`/admin/geo/states/${s.id}`, { active: v }))} />
        ))}
      </View>

      <View style={{ gap: space.sm }}>
        <Text style={label}>Cidades</Text>
        {data.cities.map((c) => (
          <GeoRow key={c.id} name={c.name} active={c.active} onToggle={(v) => act(() => adminApi.patch(`/admin/geo/cities/${c.id}`, { active: v }))} />
        ))}
        <View style={{ flexDirection: "row", gap: space.sm }}>
          <View style={{ flex: 1 }}><Field placeholder="Nova cidade (PA)..." value={newCity} onChangeText={setNewCity} /></View>
          <Btn small variant="secondary" title="Adicionar" disabled={!newCity.trim()}
               onPress={() => { act(() => adminApi.post("/admin/geo/cities", { state_id: "st-pa", name: newCity.trim() })); setNewCity(""); }} />
        </View>
      </View>

      <View style={{ gap: space.sm }}>
        <Text style={label}>Bairros e regiões · Parauapebas ({data.neighborhoods.length})</Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
          {HOOD_KINDS.map((k) => <Chip key={k} label={k} active={hoodKind === k} onPress={() => setHoodKind(k)} />)}
        </View>
        <View style={{ flexDirection: "row", gap: space.sm }}>
          <View style={{ flex: 1 }}><Field placeholder={`Novo ${hoodKind}...`} value={newHood} onChangeText={setNewHood} /></View>
          <Btn small variant="secondary" title="Adicionar" disabled={!newHood.trim()}
               onPress={() => { act(() => adminApi.post("/admin/geo/neighborhoods", { city_id: "city-parauapebas", name: newHood.trim(), kind: hoodKind })); setNewHood(""); }} />
        </View>
        {data.neighborhoods.map((h) => (
          <GeoRow key={h.id} name={`${h.name}${h.kind !== "bairro" ? ` · ${h.kind}` : ""}`} active={h.active} onToggle={(v) => act(() => adminApi.patch(`/admin/geo/neighborhoods/${h.id}`, { active: v }))} />
        ))}
      </View>
    </View>
  );
}

function GeoRow({ name, active, onToggle }: { name: string; active: boolean; onToggle: (v: boolean) => void }) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 10, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: space.md, paddingVertical: space.sm }}>
      <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 13, flex: 1 }}>{name}</Text>
      <Switch value={active} onValueChange={onToggle} trackColor={{ true: colors.primary }} />
    </View>
  );
}
