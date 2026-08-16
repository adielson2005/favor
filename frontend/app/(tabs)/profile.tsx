import { Ionicons } from "@expo/vector-icons";
import * as ImagePicker from "expo-image-picker";
import { useRouter } from "expo-router";
import React, { useMemo, useState } from "react";
import { Alert, Linking, Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Avatar, Btn, Chip, Field, Row, Segmented, Sheet, Stars } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useApp } from "@/src/state";
import { ThemePref, useTheme } from "@/src/theme";

export default function Profile() {
  const { colors, pref, setPref } = useTheme();
  const { me, mode, cities, neighborhoods, city, refreshMe } = useApp();
  const { logout, changePassword, deleteAccount } = useAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const [editOpen, setEditOpen] = useState(false);
  const [locationOpen, setLocationOpen] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  const [passwordOpen, setPasswordOpen] = useState(false);
  const [name, setName] = useState("");
  const [bio, setBio] = useState("");
  const [cityId, setCityId] = useState<string | null>(null);
  const [hood, setHood] = useState<string | null>(null);
  const [reportText, setReportText] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);

  const myHood = neighborhoods.find((n) => n.id === me?.neighborhood_id);
  const hoodsInSelectedCity = useMemo(() => neighborhoods.filter((n) => n.city_id === cityId), [neighborhoods, cityId]);

  if (!me) return null;

  const memberSince = me.member_since ? new Date(me.member_since).getFullYear() : "2025";

  const saveProfile = async () => {
    setSaving(true);
    try {
      await api.patch(`/users/${me.id}`, { name: name || undefined, bio: bio || undefined });
      refreshMe();
      setEditOpen(false);
    } catch { Alert.alert("Ops", "Não conseguimos salvar agora. Tente novamente."); } finally { setSaving(false); }
  };

  const pickAvatar = async () => {
    const current = await ImagePicker.getMediaLibraryPermissionsAsync();
    if (!current.granted) {
      if (!current.canAskAgain) {
        Alert.alert("Permissão necessária", "Para trocar a foto, permita o acesso às imagens nas configurações.", [
          { text: "Agora não" },
          { text: "Abrir configurações", onPress: () => Linking.openSettings() },
        ]);
        return;
      }
      const asked = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!asked.granted) return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], quality: 0.4, base64: true, allowsEditing: true, aspect: [1, 1] });
    if (result.canceled || !result.assets[0]?.base64) return;
    setUploadingPhoto(true);
    try {
      await api.patch(`/users/${me.id}`, { avatar_b64: `data:image/jpeg;base64,${result.assets[0].base64}` });
      refreshMe();
    } catch (e: any) {
      Alert.alert("Não foi possível atualizar a foto", e.message || "Tente novamente.");
    } finally {
      setUploadingPhoto(false);
    }
  };

  const saveLocation = async () => {
    setSaving(true);
    try {
      await api.patch(`/users/${me.id}`, { city_id: cityId || undefined, neighborhood_id: hood });
      refreshMe();
      setLocationOpen(false);
    } catch { Alert.alert("Ops", "Não conseguimos salvar agora."); } finally { setSaving(false); }
  };

  const sendReport = async () => {
    if (!reportText.trim()) return;
    setSaving(true);
    try {
      await api.post("/reports", { target_type: "user", target_id: "app", reason: "Problema no aplicativo", details: reportText });
      setReportOpen(false);
      setReportText("");
      Alert.alert("Obrigado", "Recebemos o seu relato. Vamos analisar.");
    } catch { Alert.alert("Ops", "Não conseguimos enviar agora."); } finally { setSaving(false); }
  };

  const savePassword = async () => {
    if (newPassword.length < 8) { Alert.alert("Senha muito curta", "Use pelo menos 8 caracteres."); return; }
    if (newPassword !== confirmPassword) { Alert.alert("As senhas não coincidem", "Confira e tente de novo."); return; }
    setSaving(true);
    try {
      await changePassword(currentPassword, newPassword);
      setPasswordOpen(false);
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
      Alert.alert("Pronto", "Sua senha foi alterada.");
    } catch (e: any) {
      Alert.alert("Não foi possível trocar a senha", e.message || "Confira a senha atual.");
    } finally { setSaving(false); }
  };

  const confirmDeleteAccount = () => {
    Alert.alert("Excluir conta", "Isso vai apagar seus dados pessoais e bloquear o acesso. Não é possível desfazer. Continuar?", [
      { text: "Cancelar", style: "cancel" },
      { text: "Excluir conta", style: "destructive", onPress: async () => {
        try {
          await deleteAccount();
          router.replace("/auth/welcome");
        } catch (e: any) {
          Alert.alert("Não foi possível excluir", e.message || "Tente novamente.");
        }
      } },
    ]);
  };

  const doLogout = async () => {
    await logout();
    router.replace("/auth/welcome");
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView contentContainerStyle={{ paddingTop: insets.top + 16, paddingBottom: 40, paddingHorizontal: 20 }} showsVerticalScrollIndicator={false}>
        {/* Header */}
        <View style={{ flexDirection: "row", alignItems: "center", gap: 16 }}>
          <Pressable testID="edit-avatar-button" onPress={pickAvatar} disabled={uploadingPhoto} style={{ opacity: uploadingPhoto ? 0.5 : 1 }}>
            <Avatar name={me.name} initials={me.initials} size={68} photo={me.avatar_b64} />
            <View style={{ position: "absolute", right: -2, bottom: -2, width: 24, height: 24, borderRadius: 12, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center", borderWidth: 2, borderColor: colors.bg }}>
              <Ionicons name="camera" size={12} color={colors.onPrimary} />
            </View>
          </Pressable>
          <View style={{ flex: 1, gap: 3 }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
              <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 20 }}>{me.name}</Text>
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
          <Row testID="location-row" icon="location-outline" label="Localização" value={myHood?.name || city?.name} onPress={() => { setCityId(me.city_id || city?.id || null); setHood(me.neighborhood_id || null); setLocationOpen(true); }} />
          <Row testID="change-password-row" icon="lock-closed-outline" label="Alterar senha" onPress={() => { setCurrentPassword(""); setNewPassword(""); setConfirmPassword(""); setPasswordOpen(true); }} />
          <Row icon="shield-checkmark-outline" label="Verificação" value={me.verified_identity ? "Identidade verificada" : "Pendente"} />
        </Section>

        <Section title="Financeiro">
          <Row testID="wallet-row" icon="wallet-outline" label="Minha carteira" onPress={() => router.push("/wallet")} />
          <Row testID="security-row" icon="shield-outline" label="Segurança" onPress={() => router.push("/security")} />
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
          {me.is_admin && <Row testID="admin-row" icon="settings-outline" label="Administração" onPress={() => router.push("/admin")} />}
          <Row testID="logout-row" icon="log-out-outline" label="Sair" danger onPress={doLogout} />
          <Row testID="delete-account-row" icon="trash-outline" label="Excluir conta" danger onPress={confirmDeleteAccount} />
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
          {cities.length > 1 && (
            <View style={{ gap: 8 }}>
              <Text style={{ color: colors.muted, fontFamily: fonts.bodyBold, fontSize: 12, textTransform: "uppercase", letterSpacing: 0.6 }}>Cidade</Text>
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
                {cities.map((c) => <Chip key={c.id} testID={`profile-city-${c.id}`} label={c.name} active={cityId === c.id} onPress={() => { setCityId(c.id); setHood(null); }} />)}
              </View>
            </View>
          )}
          <Text style={{ color: colors.muted, fontFamily: fonts.bodyBold, fontSize: 12, textTransform: "uppercase", letterSpacing: 0.6 }}>Bairro</Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            {hoodsInSelectedCity.map((n) => <Chip key={n.id} label={n.name} active={hood === n.id} onPress={() => setHood(n.id)} />)}
          </View>
          <Btn title="Salvar" onPress={saveLocation} loading={saving} />
        </View>
      </Sheet>

      {/* Change password */}
      <Sheet visible={passwordOpen} onClose={() => setPasswordOpen(false)} title="Alterar senha">
        <View style={{ gap: 14, paddingVertical: 12, paddingBottom: 24 }}>
          <Field label="Senha atual" value={currentPassword} onChangeText={setCurrentPassword} secureTextEntry testID="current-password-input" />
          <Field label="Nova senha" value={newPassword} onChangeText={setNewPassword} placeholder="Mínimo 8 caracteres" secureTextEntry testID="new-password-input" />
          <Field label="Confirmar nova senha" value={confirmPassword} onChangeText={setConfirmPassword} secureTextEntry testID="confirm-password-input" />
          <Btn title="Salvar" onPress={savePassword} loading={saving} disabled={!currentPassword || !newPassword || !confirmPassword} testID="save-password-button" />
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
      <Text style={{ color: colors.faint, fontFamily: fonts.bodyBold, fontSize: 12, textTransform: "uppercase", letterSpacing: 1, marginBottom: 4 }}>{title}</Text>
      <View>{children}</View>
    </View>
  );
}
