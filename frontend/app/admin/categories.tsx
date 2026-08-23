import { Ionicons } from "@expo/vector-icons";
import React, { useCallback, useEffect, useState } from "react";
import { Alert, Pressable, Switch, Text, View } from "react-native";

import { adminApi } from "@/src/admin-api";
import { fonts } from "@/src/hooks/use-app-fonts";
import { radius, space, useTheme } from "@/src/theme";
import { Btn, Field } from "@/src/components/ui";

type Subcategory = { id: string; category_id: string; name: string; active: boolean };
type Category = { id: string; name: string; icon: string; active: boolean; subcategories: Subcategory[] };

export default function AdminCategories() {
  const { colors } = useTheme();
  const [cats, setCats] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [newCat, setNewCat] = useState("");

  const load = useCallback(() => {
    adminApi.get("/admin/categories").then(setCats).catch(() => {}).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<any>) => {
    try { await fn(); load(); } catch (e: any) { Alert.alert("Ops", e.message || "Não foi possível concluir."); }
  };

  if (loading) return null;

  return (
    <View style={{ gap: space.lg, maxWidth: 640 }}>
      <View style={{ flexDirection: "row", gap: space.sm, alignItems: "flex-end" }}>
        <View style={{ flex: 1 }}><Field label="Nova categoria" placeholder="Nome da categoria" value={newCat} onChangeText={setNewCat} /></View>
        <Btn title="Adicionar" disabled={!newCat.trim()} onPress={() => { act(() => adminApi.post("/admin/categories", { name: newCat.trim() })); setNewCat(""); }} />
      </View>

      {cats.map((cat) => (
        <View key={cat.id} style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg, padding: space.lg, gap: space.md }}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
            <Ionicons name={cat.icon as any} size={18} color={colors.primary} />
            <Text style={{ color: colors.ink, fontFamily: fonts.bodyBold, fontSize: 15, flex: 1 }}>{cat.name}</Text>
            <Switch value={cat.active} onValueChange={(v) => act(() => adminApi.patch(`/admin/categories/${cat.id}`, { active: v }))} trackColor={{ true: colors.primary }} testID={`admin-category-${cat.id}-toggle`} />
          </View>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
            {cat.subcategories.map((sub) => (
              <Pressable
                key={sub.id}
                onPress={() => act(() => adminApi.patch(`/admin/subcategories/${sub.id}`, { active: !sub.active }))}
                style={{ paddingHorizontal: 10, paddingVertical: 5, borderRadius: 10, backgroundColor: sub.active ? colors.alt : "transparent", borderWidth: 1, borderColor: colors.border, opacity: sub.active ? 1 : 0.45 }}
              >
                <Text style={{ color: colors.muted, fontFamily: fonts.bodySemiBold, fontSize: 11, textDecorationLine: sub.active ? "none" : "line-through" }}>{sub.name}</Text>
              </Pressable>
            ))}
          </View>
          <NewSubcategory categoryId={cat.id} onAdd={(name) => act(() => adminApi.post("/admin/subcategories", { category_id: cat.id, name }))} />
        </View>
      ))}
    </View>
  );
}

function NewSubcategory({ onAdd }: { categoryId: string; onAdd: (name: string) => void }) {
  const [value, setValue] = useState("");
  return (
    <View style={{ flexDirection: "row", gap: space.sm }}>
      <View style={{ flex: 1 }}><Field placeholder="Nova subcategoria..." value={value} onChangeText={setValue} /></View>
      <Btn small variant="secondary" title="Adicionar" disabled={!value.trim()} onPress={() => { onAdd(value.trim()); setValue(""); }} />
    </View>
  );
}
