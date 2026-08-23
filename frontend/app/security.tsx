import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useEffect, useState } from "react";
import { Alert, Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, LinkedAccount } from "@/src/api";
import { useAuth } from "@/src/auth";
import { useApp } from "@/src/state";
import { Avatar, Btn, Field, Row, Sheet } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { extractIdToken, useGoogleAuth } from "@/src/hooks/use-google-auth";
import { useRequireAuth } from "@/src/hooks/use-require-auth";
import { radius, space, useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

function formatPhoneBR(raw: string): string {
  const digits = raw.replace(/\D/g, "").slice(0, 11);
  if (digits.length <= 2) return digits;
  if (digits.length <= 7) return `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
  return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
}

type Block = { blocked_user_id: string; user: { id: string; name: string; initials: string; avatar_b64?: string | null } | null };

export default function Security() {
  const { colors } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { me, refreshMe } = useApp();
  const { syncSession } = useAuth();
  useRequireAuth();
  const google = useGoogleAuth();

  const [blocks, setBlocks] = useState<Block[]>([]);
  useFocusEffect(useCallback(() => { api.get("/blocks").then(setBlocks).catch(() => {}); }, []));

  const [linkedAccounts, setLinkedAccounts] = useState<LinkedAccount[]>([]);
  const [linking, setLinking] = useState(false);
  const [unlinking, setUnlinking] = useState(false);
  const loadLinkedAccounts = useCallback(() => {
    api.get("/auth/linked-accounts").then((data) => setLinkedAccounts(data.accounts || [])).catch(() => {});
  }, []);
  useFocusEffect(useCallback(() => { loadLinkedAccounts(); }, [loadLinkedAccounts]));
  const googleLinked = linkedAccounts.some((a) => a.provider === "GOOGLE");

  useEffect(() => {
    // A user simply closing the Google account picker fires a "dismiss"/"cancel"
    // response, not an error — nothing to alert about.
    if (google.response?.type === "dismiss" || google.response?.type === "cancel") return;
    const idToken = extractIdToken(google.response);
    if (!idToken) return;
    (async () => {
      setLinking(true);
      try {
        await api.post("/auth/google/link", { id_token: idToken, nonce: google.nonce });
        loadLinkedAccounts();
        refreshMe();
        Alert.alert("Conta Google vinculada", "Agora você também pode entrar com essa conta Google.");
      } catch (e: any) {
        Alert.alert("Não foi possível vincular sua conta Google", e.message || "Tente novamente.");
      } finally {
        setLinking(false);
      }
    })();
  }, [google.response, google.nonce, loadLinkedAccounts, refreshMe]);

  const pressLinkGoogle = () => {
    if (!google.configured) {
      Alert.alert("Google ainda não configurado", "Defina EXPO_PUBLIC_GOOGLE_CLIENT_ID (frontend) e GOOGLE_CLIENT_ID (backend) para ativar.");
      return;
    }
    google.promptAsync();
  };

  const unlinkGoogle = () => {
    Alert.alert("Desvincular Google", "Você não vai mais poder entrar com essa conta Google.", [
      { text: "Cancelar", style: "cancel" },
      {
        text: "Desvincular", style: "destructive", onPress: async () => {
          setUnlinking(true);
          try {
            await api.del("/auth/google/unlink");
            loadLinkedAccounts();
            refreshMe();
          } catch (e: any) {
            Alert.alert("Não foi possível desvincular", e.message || "Tente novamente.");
          } finally {
            setUnlinking(false);
          }
        },
      },
    ]);
  };

  const unblock = (userId: string) => {
    Alert.alert("Desbloquear usuário", "Vocês voltam a poder se contatar. Continuar?", [
      { text: "Cancelar", style: "cancel" },
      { text: "Desbloquear", onPress: async () => { try { await api.del(`/blocks/${userId}`); setBlocks((b) => b.filter((x) => x.blocked_user_id !== userId)); } catch { Alert.alert("Ops", "Não conseguimos desbloquear agora."); } } },
    ]);
  };

  const [emailOpen, setEmailOpen] = useState(false);
  const [phoneOpen, setPhoneOpen] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [saving, setSaving] = useState(false);

  const saveEmail = async () => {
    setSaving(true);
    try {
      const data = await api.post("/auth/change-email", { email: newEmail.trim().toLowerCase(), password: currentPassword });
      // change-email revokes the caller's own session as a side effect (any OTHER
      // active session gets logged out too) — apply the fresh token the backend
      // issues in the same response so this device doesn't get logged out mid-flow.
      await syncSession(data.token, data.user);
      setEmailOpen(false);
      setNewEmail(""); setCurrentPassword("");
      router.push("/auth/verify-email");
    } catch (e: any) {
      Alert.alert("Não foi possível alterar o e-mail", e.message || "Confira a senha e tente novamente.");
    } finally {
      setSaving(false);
    }
  };

  const savePhone = async () => {
    setSaving(true);
    try {
      const data = await api.post("/auth/change-phone", { phone: newPhone.replace(/\D/g, ""), password: currentPassword });
      await syncSession(data.token, data.user);
      setPhoneOpen(false);
      setNewPhone(""); setCurrentPassword("");
      router.push("/auth/verify-phone");
    } catch (e: any) {
      Alert.alert("Não foi possível alterar o telefone", e.message || "Confira a senha e tente novamente.");
    } finally {
      setSaving(false);
    }
  };

  if (!me) return null;

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + space.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: space.xl, height: 48, gap: space.md }}>
        <Pressable testID="security-back-button" onPress={() => safeBack(router, "/(tabs)/profile")} hitSlop={10}>
          <Ionicons name="arrow-back" size={24} color={colors.ink} />
        </Pressable>
        <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 17, flex: 1 }}>Segurança</Text>
      </View>

      <ScrollView contentContainerStyle={{ padding: space.xl, gap: space.xl }}>
        <View>
          <SectionTitle title="Conta" />
          <View style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, overflow: "hidden" }}>
            <StatusRow testID="security-email-status" icon="mail-outline" label="E-mail verificado" ok={me.verified_email} onPress={me.verified_email ? undefined : () => router.push("/auth/verify-email")} />
            <Divider />
            <StatusRow testID="security-phone-status" icon="call-outline" label="Telefone verificado" ok={me.verified_phone} onPress={me.verified_phone ? undefined : () => router.push("/auth/verify-phone")} />
            <Divider />
            <StatusRow icon="shield-checkmark-outline" label="Identidade verificada" ok={me.verified_identity} />
          </View>
        </View>

        <View>
          <SectionTitle title="Contas conectadas" />
          <View style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, overflow: "hidden" }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: space.md, paddingHorizontal: space.lg, height: 60 }}>
              <Ionicons name="logo-google" size={19} color={colors.muted} />
              <View style={{ flex: 1 }}>
                <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 14 }}>Google</Text>
                <Text style={{ color: googleLinked ? colors.green : colors.faint, fontFamily: fonts.bodySemiBold, fontSize: 12, marginTop: 2 }}>
                  {googleLinked ? "✓ Conectado" : "Não conectado"}
                </Text>
              </View>
              {googleLinked ? (
                <Pressable testID="security-google-unlink" onPress={unlinkGoogle} disabled={unlinking} hitSlop={8}>
                  <Text style={{ color: colors.danger, fontFamily: fonts.bodyBold, fontSize: 13 }}>{unlinking ? "..." : "Desvincular"}</Text>
                </Pressable>
              ) : (
                <Pressable testID="security-google-link" onPress={pressLinkGoogle} disabled={linking} hitSlop={8}>
                  <Text style={{ color: colors.primary, fontFamily: fonts.bodyBold, fontSize: 13 }}>{linking ? "..." : "Vincular"}</Text>
                </Pressable>
              )}
            </View>
          </View>
        </View>

        <View>
          <SectionTitle title="Acesso" />
          <View style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, overflow: "hidden" }}>
            <Row icon="lock-closed-outline" label="Alterar senha" onPress={() => router.push("/(tabs)/profile")} />
            <Divider />
            <Row testID="security-change-email-row" icon="mail-outline" label="Alterar e-mail" onPress={() => { setNewEmail(""); setCurrentPassword(""); setEmailOpen(true); }} />
            <Divider />
            <Row testID="security-change-phone-row" icon="call-outline" label="Alterar telefone" onPress={() => { setNewPhone(""); setCurrentPassword(""); setPhoneOpen(true); }} />
          </View>
          <Text style={{ color: colors.faint, fontSize: 12, marginTop: space.sm }}>Use "Alterar senha" no seu perfil para trocar a senha atual.</Text>
        </View>

        <View>
          <SectionTitle title="Dados financeiros" />
          <View style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, overflow: "hidden" }}>
            <Row testID="security-bank-accounts-row" icon="card-outline" label="Contas para saque" onPress={() => router.push("/wallet/bank-accounts")} />
            <Divider />
            <Row testID="security-extract-row" icon="receipt-outline" label="Atividade da carteira" onPress={() => router.push("/wallet/extract")} />
          </View>
        </View>

        <View>
          <SectionTitle title="Usuários bloqueados" />
          {blocks.length === 0 ? (
            <Text style={{ color: colors.faint, fontSize: 13 }}>Você não bloqueou ninguém.</Text>
          ) : (
            <View style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, overflow: "hidden" }}>
              {blocks.map((b, i) => (
                <View key={b.blocked_user_id}>
                  {i > 0 && <Divider />}
                  <View style={{ flexDirection: "row", alignItems: "center", gap: space.md, paddingHorizontal: space.lg, height: 60 }}>
                    <Avatar name={b.user?.name} initials={b.user?.initials} size={36} photo={b.user?.avatar_b64} />
                    <Text style={{ flex: 1, color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 14 }}>{b.user?.name || "Usuário"}</Text>
                    <Pressable testID="unblock-user-button" onPress={() => unblock(b.blocked_user_id)} hitSlop={8}>
                      <Text style={{ color: colors.primary, fontFamily: fonts.bodyBold, fontSize: 13 }}>Desbloquear</Text>
                    </Pressable>
                  </View>
                </View>
              ))}
            </View>
          )}
        </View>
      </ScrollView>

      <Sheet visible={emailOpen} onClose={() => setEmailOpen(false)} title="Alterar e-mail">
        <View style={{ gap: 14, paddingVertical: 12, paddingBottom: 24 }}>
          <Field label="Novo e-mail" value={newEmail} onChangeText={setNewEmail} placeholder="voce@email.com" autoCapitalize="none" keyboardType="email-address" testID="change-email-input" />
          <Field label="Senha atual" value={currentPassword} onChangeText={setCurrentPassword} secureTextEntry testID="change-email-password-input" />
          <Btn title="Salvar" onPress={saveEmail} loading={saving} disabled={!newEmail.trim() || !currentPassword} testID="save-email-button" />
        </View>
      </Sheet>

      <Sheet visible={phoneOpen} onClose={() => setPhoneOpen(false)} title="Alterar telefone">
        <View style={{ gap: 14, paddingVertical: 12, paddingBottom: 24 }}>
          <Field label="Novo telefone" value={newPhone} onChangeText={(v) => setNewPhone(formatPhoneBR(v))} placeholder="(94) 99999-9999" keyboardType="phone-pad" testID="change-phone-input" />
          <Field label="Senha atual" value={currentPassword} onChangeText={setCurrentPassword} secureTextEntry testID="change-phone-password-input" />
          <Btn title="Salvar" onPress={savePhone} loading={saving} disabled={!newPhone.trim() || !currentPassword} testID="save-phone-button" />
        </View>
      </Sheet>
    </View>
  );
}

function SectionTitle({ title }: { title: string }) {
  const { colors } = useTheme();
  return <Text style={{ color: colors.faint, fontFamily: fonts.bodyBold, fontSize: 12, textTransform: "uppercase", letterSpacing: 1, marginBottom: space.sm }}>{title}</Text>;
}

function Divider() {
  const { colors } = useTheme();
  return <View style={{ height: 1, backgroundColor: colors.border, marginLeft: space.xl + 24 }} />;
}

function StatusRow({ icon, label, ok, onPress, testID }: { icon: keyof typeof Ionicons.glyphMap; label: string; ok?: boolean; onPress?: () => void; testID?: string }) {
  const { colors } = useTheme();
  const Container = onPress ? Pressable : View;
  return (
    <Container testID={testID} onPress={onPress} style={{ flexDirection: "row", alignItems: "center", gap: space.md, paddingHorizontal: space.lg, height: 52 }}>
      <Ionicons name={icon} size={19} color={colors.muted} />
      <Text style={{ flex: 1, color: colors.ink, fontFamily: fonts.body, fontSize: 14 }}>{label}</Text>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
        <Ionicons name={ok ? "checkmark-circle" : "close-circle-outline"} size={16} color={ok ? colors.green : colors.faint} />
        <Text style={{ color: ok ? colors.green : colors.faint, fontFamily: fonts.bodySemiBold, fontSize: 12 }}>{ok ? "Verificado" : "Pendente"}</Text>
      </View>
      {onPress && <Ionicons name="chevron-forward" size={16} color={colors.faint} />}
    </Container>
  );
}
