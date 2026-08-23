import { Ionicons } from "@expo/vector-icons";
import * as ImagePicker from "expo-image-picker";
import { useRouter } from "expo-router";
import React, { useMemo, useState } from "react";
import { Alert, Linking, Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Animated, { FadeInDown } from "react-native-reanimated";

import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { AvatarCropModal } from "@/src/components/AvatarCropModal";
import { Avatar, Btn, Chip, Field, Sheet, Stars } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useBreakpoint } from "@/src/hooks/use-breakpoint";
import { useApp } from "@/src/state";
import { radius, space, useTheme } from "@/src/theme";

type Icon = keyof typeof Ionicons.glyphMap;

export default function Profile() {
  const { colors } = useTheme();
  const { me, mode, cities, neighborhoods, city, refreshMe } = useApp();
  const { changePassword, logout } = useAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { isDesktop } = useBreakpoint();

  const [editOpen, setEditOpen] = useState(false);
  const [locationOpen, setLocationOpen] = useState(false);
  const [passwordOpen, setPasswordOpen] = useState(false);
  const [name, setName] = useState("");
  const [bio, setBio] = useState("");
  const [cityId, setCityId] = useState<string | null>(null);
  const [hood, setHood] = useState<string | null>(null);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [cropUri, setCropUri] = useState<string | null>(null);

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
    // No native allowsEditing here — its crop UI is iOS/Android-only and silently does
    // nothing on web. AvatarCropModal below gives the same drag-to-reposition +
    // zoom-to-adjust experience on every platform instead of two different flows.
    const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"] });
    if (result.canceled || !result.assets[0]?.uri) return;
    setCropUri(result.assets[0].uri);
  };

  const confirmAvatarCrop = async (base64: string) => {
    setCropUri(null);
    setUploadingPhoto(true);
    try {
      await api.patch(`/users/${me.id}`, { avatar_b64: base64 });
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

  const savePassword = async () => {
    if (newPassword.length < 8) { Alert.alert("Senha muito curta", "Use pelo menos 8 caracteres."); return; }
    if (newPassword !== confirmPassword) { Alert.alert("As senhas não coincidem", "Confira e tente de novo."); return; }
    const wasCreating = !me.has_password;
    setSaving(true);
    try {
      await changePassword(currentPassword, newPassword);
      setPasswordOpen(false);
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
      // The backend invalidates this session as part of the password change, so the
      // cached token is already stale — log out and send the user to log in again.
      await logout();
      Alert.alert("Pronto", wasCreating ? "Sua senha foi criada. Entre novamente." : "Sua senha foi alterada. Entre novamente.");
      router.replace("/auth/welcome");
    } catch (e: any) {
      Alert.alert(wasCreating ? "Não foi possível criar a senha" : "Não foi possível trocar a senha", e.message || "Tente novamente.");
    } finally { setSaving(false); }
  };

  const stats = [
    { label: "Avaliação", value: String(me.rating) },
    { label: "Serviços", value: String(me.jobs_done) },
    { label: "Desde", value: String(memberSince) },
  ];

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView contentContainerStyle={{ paddingTop: insets.top + 16, paddingBottom: 40, paddingHorizontal: 20, width: "100%", maxWidth: isDesktop ? 720 : undefined, alignSelf: "center" }} showsVerticalScrollIndicator={false}>
        <View style={{ flexDirection: "row", justifyContent: "flex-end" }}>
          <Pressable testID="open-settings-button" onPress={() => router.push("/settings")} hitSlop={10} style={{ width: 36, height: 36, borderRadius: 18, alignItems: "center", justifyContent: "center" }}>
            <Ionicons name="settings-outline" size={20} color={colors.muted} />
          </Pressable>
        </View>

        {/* Header — centered, no chrome, lets whitespace and type do the work */}
        <Animated.View entering={FadeInDown.duration(280)} style={{ alignItems: "center", marginTop: -8 }}>
          <Pressable testID="edit-avatar-button" onPress={pickAvatar} disabled={uploadingPhoto} style={{ opacity: uploadingPhoto ? 0.5 : 1 }}>
            <Avatar name={me.name} initials={me.initials} size={92} photo={me.avatar_b64} />
            <View style={{ position: "absolute", right: -2, bottom: -2, width: 30, height: 30, borderRadius: 15, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center", borderWidth: 3, borderColor: colors.bg }}>
              <Ionicons name="camera" size={14} color={colors.onPrimary} />
            </View>
          </Pressable>

          <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginTop: space.md }}>
            <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 22 }}>{me.name}</Text>
            {me.verified_identity && <Ionicons name="checkmark-circle" size={18} color={colors.green} />}
          </View>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginTop: 5 }}>
            <Stars value={me.rating} size={13} />
            <Text style={{ color: colors.muted, fontSize: 13 }}>{me.rating} ({me.rating_count})</Text>
          </View>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 4, marginTop: 5 }}>
            <Ionicons name="location-outline" size={13} color={colors.faint} />
            <Text style={{ color: colors.muted, fontSize: 13 }}>{myHood?.name ? `${myHood.name} · ` : ""}{city?.name || "Parauapebas"}, PA</Text>
          </View>

          <View style={{ flexDirection: "row", gap: 8, marginTop: space.md }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 4, backgroundColor: colors.primarySoft, paddingHorizontal: 10, paddingVertical: 6, borderRadius: radius.pill }}>
              <Ionicons name="ribbon-outline" size={12} color={colors.primary} />
              <Text style={{ color: colors.primary, fontFamily: fonts.bodyBold, fontSize: 12 }}>{me.level}</Text>
            </View>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 4, backgroundColor: colors.alt, paddingHorizontal: 10, paddingVertical: 6, borderRadius: radius.pill }}>
              <Ionicons name={mode === "client" ? "person-outline" : "hammer-outline"} size={12} color={colors.muted} />
              <Text style={{ color: colors.muted, fontFamily: fonts.bodySemiBold, fontSize: 12 }}>{mode === "client" ? "Cliente" : "Fazedor"}</Text>
            </View>
          </View>

          {me.bio ? <Text style={{ color: colors.muted, fontSize: 14, lineHeight: 20, marginTop: space.md, textAlign: "center", paddingHorizontal: space.lg }}>{me.bio}</Text> : null}
        </Animated.View>

        {/* Stats — hairline dividers only, no card */}
        <Animated.View entering={FadeInDown.delay(70).duration(280)} style={{ flexDirection: "row", justifyContent: "center", marginTop: space.xxl }}>
          {stats.map((stat, i) => (
            <View key={stat.label} style={{ alignItems: "center", paddingHorizontal: space.xl, borderLeftWidth: i ? 1 : 0, borderLeftColor: colors.border }}>
              <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 19 }}>{stat.value}</Text>
              <Text style={{ color: colors.faint, fontSize: 12, marginTop: 2 }}>{stat.label}</Text>
            </View>
          ))}
        </Animated.View>

        {/* Sections — grouped by whitespace and a shared row style, not boxes */}
        <Animated.View entering={FadeInDown.delay(120).duration(280)}>
          <Section title="Minha conta">
            <ProfileRow testID="edit-profile-row" icon="person-outline" label="Editar perfil" onPress={() => { setName(me.name); setBio(me.bio || ""); setEditOpen(true); }} />
            <ProfileRow testID="location-row" icon="location-outline" label="Localização" value={myHood?.name || city?.name} onPress={() => { setCityId(me.city_id || city?.id || null); setHood(me.neighborhood_id || null); setLocationOpen(true); }} />
            <ProfileRow testID="change-password-row" icon="lock-closed-outline" label="Alterar senha" onPress={() => { setCurrentPassword(""); setNewPassword(""); setConfirmPassword(""); setPasswordOpen(true); }} />
            <ProfileRow icon="shield-checkmark-outline" label="Verificação" value={me.verified_identity ? "Identidade verificada" : "Pendente"} valueColor={me.verified_identity ? colors.green : undefined} />
          </Section>
        </Animated.View>

        <Animated.View entering={FadeInDown.delay(160).duration(280)}>
          <Section title="Financeiro">
            <ProfileRow testID="wallet-row" icon="wallet-outline" label="fazumPay" value="Minha carteira" onPress={() => router.push("/wallet")} />
          </Section>
        </Animated.View>

        <Animated.View entering={FadeInDown.delay(200).duration(280)}>
          <Section title="Minha atividade">
            <ProfileRow testID="my-orders-row" icon="document-text-outline" label="Meus pedidos" onPress={() => router.push({ pathname: "/activity", params: { tab: "orders" } })} />
            <ProfileRow icon="construct-outline" label="Meus serviços" onPress={() => router.push({ pathname: "/activity", params: { tab: "jobs" } })} />
            <ProfileRow icon="heart-outline" label="Favoritos" onPress={() => router.push({ pathname: "/activity", params: { tab: "favorites" } })} />
            <ProfileRow icon="star-outline" label="Avaliações" onPress={() => router.push({ pathname: "/activity", params: { tab: "reviews" } })} />
          </Section>
        </Animated.View>
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
      <Sheet visible={passwordOpen} onClose={() => setPasswordOpen(false)} title={me.has_password ? "Alterar senha" : "Criar senha"}>
        <View style={{ gap: 14, paddingVertical: 12, paddingBottom: 24 }}>
          {!me.has_password && (
            <Text style={{ color: colors.muted, fontSize: 13, lineHeight: 19 }}>
              Sua conta ainda não tem senha (você entra só com o Google). Crie uma para também poder entrar com e-mail ou telefone.
            </Text>
          )}
          {me.has_password && (
            <Field label="Senha atual" value={currentPassword} onChangeText={setCurrentPassword} secureTextEntry testID="current-password-input" />
          )}
          <Field label="Nova senha" value={newPassword} onChangeText={setNewPassword} placeholder="Mínimo 8 caracteres" secureTextEntry testID="new-password-input" />
          <Field label="Confirmar nova senha" value={confirmPassword} onChangeText={setConfirmPassword} secureTextEntry testID="confirm-password-input" />
          <Btn title="Salvar" onPress={savePassword} loading={saving} disabled={(me.has_password && !currentPassword) || !newPassword || !confirmPassword} testID="save-password-button" />
        </View>
      </Sheet>

      <AvatarCropModal visible={!!cropUri} uri={cropUri} onCancel={() => setCropUri(null)} onConfirm={confirmAvatarCrop} />
    </View>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  const { colors } = useTheme();
  const items = React.Children.toArray(children);
  return (
    <View style={{ marginTop: space.xxl }}>
      <Text style={{ color: colors.faint, fontFamily: fonts.bodyBold, fontSize: 12, textTransform: "uppercase", letterSpacing: 1, marginBottom: space.sm }}>{title}</Text>
      <View>
        {items.map((child, i) => (
          <React.Fragment key={i}>
            {i > 0 && <View style={{ height: 1, backgroundColor: colors.border, marginLeft: 34 + space.md }} />}
            {child}
          </React.Fragment>
        ))}
      </View>
    </View>
  );
}

function ProfileRow({ icon, label, value, valueColor, onPress, danger, testID }: {
  icon: Icon; label: string; value?: string; valueColor?: string; onPress?: () => void; danger?: boolean; testID?: string;
}) {
  const { colors } = useTheme();
  return (
    <Pressable testID={testID} onPress={onPress} disabled={!onPress} style={({ pressed }) => [{ flexDirection: "row", alignItems: "center", gap: space.md, minHeight: 56, opacity: pressed ? 0.6 : 1 }]}>
      <View style={{ width: 34, height: 34, borderRadius: 17, backgroundColor: danger ? colors.dangerSoft : colors.alt, alignItems: "center", justifyContent: "center" }}>
        <Ionicons name={icon} size={16} color={danger ? colors.danger : colors.muted} />
      </View>
      <Text style={{ flex: 1, color: danger ? colors.danger : colors.ink, fontFamily: fonts.bodyMedium, fontSize: 15 }}>{label}</Text>
      {value ? <Text style={{ color: valueColor || colors.faint, fontFamily: fonts.bodyMedium, fontSize: 13 }}>{value}</Text> : null}
      {onPress ? <Ionicons name="chevron-forward" size={16} color={colors.faint} /> : null}
    </Pressable>
  );
}
