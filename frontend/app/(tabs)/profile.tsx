import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import { Alert, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { Avatar, Btn, Chip, Field, Row, Segmented, Sheet, Stars } from "@/src/components/ui";
import { useApp } from "@/src/state";
import { ThemePref, useTheme } from "@/src/theme";
import { storage } from "@/src/utils/storage";

export default function Profile() {
  const { colors, pref, setPref } = useTheme();
  const { me, mode, neighborhoods, city, refreshMe } = useApp();
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const [editOpen, setEditOpen] = useState(false);
  const [locationOpen, setLocationOpen] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  const [name, setName] = useState("");
  const [bio, setBio] = useState("");
  const [hood, setHood] = useState<string | null>(null);
  const [reportText, setReportText] = useState("");
  const [saving, setSaving] = useState(false);

  const myHood = neighborhoods.find((n) => n.id === me.neighborhood_id);
  const memberSince = me.member_since ? new Date(me.member_since).getFullYear() : "2025";

  const saveProfile = async () => {
    setSaving(true);
    try {
      await api.patch(`/users/${me.id}`, { name: name || undefined, bio: bio || undefined });
      refreshMe();
      setEditOpen(false);
    } catch { Alert.alert("Ops", "Não conseguimos salvar agora. Tente novamente."); } finally { setSaving(false); }
  };

  const saveLocation = async () => {
    if (!hood) return setLocationOpen(false);
    setSaving(true);
    try {
      await api.patch(`/users/${me.id}`, { neighborhood_id: hood });
      refreshMe();
      setLocationOpen(false);
    } catch { Alert.alert("Ops", "Não conseguimos salvar agora."); } finally { setSaving(false); }
  };

  const sendReport = async () => {
    if (!reportText.trim()) return;
    setSaving(true);
    try {
      await api.post("/reports", { reporter_id: me.id, target_type: "user", target_id: "app", reason: "Problema no aplicativo", details: reportText });
      setReportOpen(false);
      setReportText("");
      Alert.alert("Obrigado", "Recebemos o seu relato. Vamos analisar.");
    } catch { Alert.alert("Ops", "Não conseguimos enviar agora."); } finally { setSaving(false); }
  };

  const logout = async () => {
    await storage.removeItem("faze:onboarded");
    router.replace("/onboarding");
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView contentContainerStyle={{ paddingTop: insets.top + 16, paddingBottom: 40, paddingHorizontal: 20 }} showsVerticalScrollIndicator={false}>
        {/* Header */}
        <View style={{ flexDirection: "row", alignItems: "center", gap: 16 }}>
          <Avatar name={me.name} initials={me.initials} size={68} />
          <View style={{ flex: 1, gap: 3 }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
              <Text style={{ color: colors.ink, fontSize: 20, fontWeight: "800" }}>{me.name}</Text>
              {me.verified_identity && <Ionicons name="checkmark-circle" size={17} color={colors.green} />}
            </View>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
              <Stars value={me.rating} size={13} />
              <Text style={{ color: colors.muted, fontSize: 13 }}>{me.rating} ({me.rating_count})</Text>
            </View>
            <Text style={{ color: colors.muted, fontSize: 13 }}>{myHood?.name ? `${myHood.name} · ` : ""}{city?.name || "Parauapebas"}, PA</Text>
          </View>
        </View>
        <View style={{ flexDirection: "row", gap: 8, marginTop: 12 }}>
          <View style={{ backgroundColor: colors.primarySoft, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 10 }}>
            <Text style={{ color: colors.primary, fontSize: 12, fontWeight: "700" }}>{me.level}</Text>
          </View>
          <View style={{ backgroundColor: colors.alt, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 10 }}>
            <Text style={{ color: colors.muted, fontSize: 12, fontWeight: "600" }}>{mode === "client" ? "Cliente" : "Fazedor"}</Text>
          </View>
        </View>
        {me.bio ? <Text style={{ color: colors.muted, fontSize: 14, lineHeight: 20, marginTop: 12 }}>{me.bio}</Text> : null}

        {/* Stats */}
        <View style={{ flexDirection: "row", backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 16, marginTop: 18, paddingVertical: 14 }}>
          {[
            { label: "Avaliação", value: String(me.rating) },
            { label: "Serviços", value: String(me.jobs_done) },
            { label: "Desde", value: String(memberSince) },
          ].map((stat, i) => (
            <View key={stat.label} style={{ flex: 1, alignItems: "center", gap: 2, borderLeftWidth: i ? 1 : 0, borderLeftColor: colors.border }}>
              <Text style={{ color: colors.ink, fontSize: 17, fontWeight: "800" }}>{stat.value}</Text>
              <Text style={{ color: colors.faint, fontSize: 12 }}>{stat.label}</Text>
            </View>
          ))}
        </View>

        {/* Sections */}
        <Section title="Minha conta">
          <Row testID="edit-profile-row" icon="person-outline" label="Editar perfil" onPress={() => { setName(me.name); setBio(me.bio || ""); setEditOpen(true); }} />
          <Row testID="location-row" icon="location-outline" label="Localização" value={myHood?.name || city?.name} onPress={() => { setHood(me.neighborhood_id || null); setLocationOpen(true); }} />
          <Row icon="shield-checkmark-outline" label="Verificação" value={me.verified_identity ? "Identidade verificada" : "Pendente"} />
        </Section>

        <Section title="Minha atividade">
          <Row testID="my-orders-row" icon="document-text-outline" label="Meus pedidos" onPress={() => router.push({ pathname: "/activity", params: { tab: "orders" } })} />
          <Row icon="construct-outline" label="Meus serviços" onPress={() => router.push({ pathname: "/activity", params: { tab: "jobs" } })} />
          <Row icon="heart-outline" label="Favoritos" onPress={() => router.push({ pathname: "/activity", params: { tab: "favorites" } })} />
          <Row icon="star-outline" label="Avaliações" onPress={() => router.push({ pathname: "/activity", params: { tab: "reviews" } })} />
        </Section>

        <Section title="Preferências">
          <View style={{ paddingVertical: 10, gap: 10 }}>
            <Text style={{ color: colors.ink, fontSize: 15, fontWeight: "500" }}>Aparência</Text>
            <Segmented<ThemePref>
              options={[{ key: "light", label: "Claro" }, { key: "dark", label: "Escuro" }, { key: "system", label: "Sistema" }]}
              value={pref}
              onChange={setPref}
            />
          </View>
        </Section>

        <Section title="Ajuda">
          <Row testID="report-problem-row" icon="flag-outline" label="Denunciar problema" onPress={() => setReportOpen(true)} />
          <Row testID="admin-row" icon="settings-outline" label="Administração" value="demo" onPress={() => router.push("/admin")} />
          <Row testID="logout-row" icon="log-out-outline" label="Sair" danger onPress={logout} />
        </Section>
      </ScrollView>

      {/* Edit profile */}
      <Sheet visible={editOpen} onClose={() => setEditOpen(false)} title="Editar perfil">
        <View style={{ gap: 14, paddingVertical: 12, paddingBottom: 24 }}>
          <Field label="Nome" value={name} onChangeText={setName} testID="edit-name-input" />
          <Field label="Descrição" value={bio} onChangeText={setBio} multiline style={{ minHeight: 90, textAlignVertical: "top" }} testID="edit-bio-input" />
          <Btn title="Salvar" onPress={saveProfile} loading={saving} testID="save-profile-button" />
        </View>
      </Sheet>

      {/* Location */}
      <Sheet visible={locationOpen} onClose={() => setLocationOpen(false)} title="Localização">
        <View style={{ gap: 14, paddingVertical: 12, paddingBottom: 24 }}>
          <Text style={{ color: colors.muted, fontSize: 13 }}>Pará · {city?.name || "Parauapebas"}</Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            {neighborhoods.map((n) => <Chip key={n.id} label={n.name} active={hood === n.id} onPress={() => setHood(n.id)} />)}
          </View>
          <Btn title="Salvar" onPress={saveLocation} loading={saving} />
        </View>
      </Sheet>

      {/* Report */}
      <Sheet visible={reportOpen} onClose={() => setReportOpen(false)} title="Denunciar problema">
        <View style={{ gap: 14, paddingVertical: 12, paddingBottom: 24 }}>
          <Field label="O que aconteceu?" value={reportText} onChangeText={setReportText} multiline style={{ minHeight: 110, textAlignVertical: "top" }} placeholder="Descreva o problema..." testID="report-input" />
          <Btn title="Enviar" onPress={sendReport} loading={saving} disabled={!reportText.trim()} testID="send-report-button" />
        </View>
      </Sheet>
    </View>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  const { colors } = useTheme();
  return (
    <View style={{ marginTop: 26 }}>
      <Text style={{ color: colors.faint, fontSize: 12, fontWeight: "800", textTransform: "uppercase", letterSpacing: 1, marginBottom: 4 }}>{title}</Text>
      <View>{children}</View>
    </View>
  );
}
