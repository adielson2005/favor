import { Ionicons } from "@expo/vector-icons";
import Constants from "expo-constants";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { Alert, Linking, Pressable, ScrollView, Switch, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Btn, Field, Segmented, Sheet } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useApp } from "@/src/state";
import { radius, space, ThemePref, useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

type Icon = keyof typeof Ionicons.glyphMap;

// "security" (login/password/device alerts) is intentionally not in this list —
// those stay mandatory rather than silenceable.
const NOTIFICATION_TYPES: { key: string; label: string }[] = [
  { key: "message", label: "Novas mensagens" },
  { key: "proposal", label: "Novas propostas" },
  { key: "accept", label: "Proposta aceita" },
  { key: "reject", label: "Proposta recusada" },
  { key: "status", label: "Status do pedido" },
  { key: "review", label: "Avaliações" },
  { key: "payment", label: "Pagamentos" },
  { key: "refund", label: "Reembolsos" },
  { key: "earning", label: "Novos ganhos" },
  { key: "withdrawal", label: "Saques" },
  { key: "bank_account", label: "Contas bancárias" },
  { key: "adjustment", label: "Ajustes na carteira" },
  { key: "dispute", label: "Disputas" },
];

export default function Settings() {
  const { colors, pref, setPref } = useTheme();
  const { me } = useApp();
  const { logout, deleteAccount } = useAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const [reportOpen, setReportOpen] = useState(false);
  const [reportText, setReportText] = useState("");
  const [aboutOpen, setAboutOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const [notifPrefs, setNotifPrefs] = useState<Record<string, boolean>>({});
  useFocusEffect(useCallback(() => { api.get("/auth/notification-prefs").then((r) => setNotifPrefs(r.prefs || {})).catch(() => {}); }, []));

  const toggleNotifPref = async (key: string, value: boolean) => {
    const next = { ...notifPrefs, [key]: value };
    setNotifPrefs(next);
    try { await api.patch("/auth/notification-prefs", { prefs: next }); } catch { setNotifPrefs(notifPrefs); }
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

  const doLogout = async () => {
    await logout();
    router.replace("/auth/welcome");
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

  if (!me) return null;

  const version = Constants.expoConfig?.version || "1.0.0";

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + 12 }}>
      <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: 20, gap: 14 }}>
        <Pressable testID="settings-back-button" onPress={() => safeBack(router, "/(tabs)/profile")} hitSlop={10}>
          <Ionicons name="arrow-back" size={24} color={colors.ink} />
        </Pressable>
        <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: colors.ink, alignItems: "center", justifyContent: "center" }}>
          <Ionicons name="settings" size={18} color={colors.bg} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 19, letterSpacing: -0.3 }}>Configurações</Text>
          <Text style={{ color: colors.faint, fontSize: 12 }}>Conta, privacidade e preferências</Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={{ padding: 20, paddingBottom: 40 }} showsVerticalScrollIndicator={false}>
        <CardSection title="Conta">
          <SettingsRow testID="settings-security-row" icon="shield-checkmark-outline" label="Privacidade e segurança" onPress={() => router.push("/security")} />
          <Divider />
          <SettingsRow testID="settings-payment-methods-row" icon="card-outline" label="Contas para saque" onPress={() => router.push("/wallet/bank-accounts")} last />
        </CardSection>

        <CardSection title="Preferências">
          <View style={{ paddingHorizontal: space.lg, paddingVertical: space.md, gap: 10 }}>
            <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 14 }}>Aparência</Text>
            <Segmented<ThemePref>
              options={[{ key: "light", label: "Claro" }, { key: "dark", label: "Escuro" }, { key: "system", label: "Sistema" }]}
              value={pref}
              onChange={setPref}
            />
          </View>
          <Divider />
          <SettingsRow icon="language-outline" label="Idioma" value="Português (Brasil)" last />
        </CardSection>

        <CardSection title="Notificações">
          {NOTIFICATION_TYPES.map((t, i) => (
            <React.Fragment key={t.key}>
              {i > 0 && <Divider />}
              <SwitchRow label={t.label} value={notifPrefs[t.key] !== false} onChange={(v) => toggleNotifPref(t.key, v)} />
            </React.Fragment>
          ))}
        </CardSection>

        <CardSection title="Suporte">
          <SettingsRow testID="settings-report-row" icon="flag-outline" label="Denunciar um problema" onPress={() => setReportOpen(true)} />
          <Divider />
          <SettingsRow testID="settings-contact-row" icon="mail-outline" label="Fale conosco" onPress={() => Linking.openURL("mailto:suporte@fazum.app")} />
          <Divider />
          <SettingsRow testID="settings-about-row" icon="information-circle-outline" label="Sobre o app" onPress={() => setAboutOpen(true)} last={!me.is_admin} />
          {me.is_admin && (
            <>
              <Divider />
              <SettingsRow testID="settings-admin-row" icon="construct-outline" label="Administração" onPress={() => router.push("/admin")} last />
            </>
          )}
        </CardSection>

        <View style={{ marginTop: 24 }}>
          <Text style={{ color: colors.danger, fontFamily: fonts.bodyBold, fontSize: 12, textTransform: "uppercase", letterSpacing: 1, marginBottom: 4 }}>Zona de risco</Text>
          <View style={{ backgroundColor: colors.dangerSoft, borderWidth: 1, borderColor: colors.danger, borderRadius: radius.lg, overflow: "hidden" }}>
            <SettingsRow testID="settings-logout-row" icon="log-out-outline" label="Sair" danger onPress={doLogout} />
            <Divider danger />
            <SettingsRow testID="settings-delete-account-row" icon="trash-outline" label="Excluir conta" danger onPress={confirmDeleteAccount} last />
          </View>
        </View>
      </ScrollView>

      <Sheet visible={reportOpen} onClose={() => setReportOpen(false)} title="Denunciar problema">
        <View style={{ gap: 14, paddingVertical: 12, paddingBottom: 24 }}>
          <Field label="O que aconteceu?" value={reportText} onChangeText={setReportText} multiline style={{ minHeight: 110, textAlignVertical: "top" }} placeholder="Descreva o problema..." testID="settings-report-input" />
          <Btn title="Enviar" onPress={sendReport} loading={saving} disabled={!reportText.trim()} testID="settings-send-report-button" />
        </View>
      </Sheet>

      <Sheet visible={aboutOpen} onClose={() => setAboutOpen(false)} title="Sobre o app">
        <View style={{ gap: 10, paddingVertical: 12, paddingBottom: 24 }}>
          <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 20 }}>fazum</Text>
          <Text style={{ color: colors.muted, fontSize: 14, lineHeight: 20 }}>
            Conectamos quem precisa de ajuda com quem pode ajudar, perto de você.
          </Text>
          <Text style={{ color: colors.faint, fontSize: 12, marginTop: 6 }}>Versão {version}</Text>
        </View>
      </Sheet>
    </View>
  );
}

// A bordered card grouping rows — deliberately distinct from the Profile tab's bare
// list-with-labels look, closer to how these apps separate "Configurações" as its
// own surface rather than an extension of the profile screen.
function CardSection({ title, children }: { title: string; children: React.ReactNode }) {
  const { colors } = useTheme();
  return (
    <View style={{ marginTop: 24 }}>
      <Text style={{ color: colors.faint, fontFamily: fonts.bodyBold, fontSize: 12, textTransform: "uppercase", letterSpacing: 1, marginBottom: 4 }}>{title}</Text>
      <View style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg, overflow: "hidden" }}>
        {children}
      </View>
    </View>
  );
}

function Divider({ danger }: { danger?: boolean }) {
  const { colors } = useTheme();
  return <View style={{ height: 1, backgroundColor: danger ? colors.danger : colors.border, opacity: danger ? 0.25 : 1, marginLeft: space.lg + 32 + 12 }} />;
}

function SwitchRow({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 12, minHeight: 52, paddingHorizontal: space.lg }}>
      <Text style={{ flex: 1, color: colors.ink, fontFamily: fonts.body, fontSize: 14 }}>{label}</Text>
      <Switch value={value} onValueChange={onChange} trackColor={{ false: colors.border, true: colors.primary }} />
    </View>
  );
}

function SettingsRow({ icon, label, value, onPress, danger, last, testID }: {
  icon: Icon; label: string; value?: string; onPress?: () => void; danger?: boolean; last?: boolean; testID?: string;
}) {
  const { colors } = useTheme();
  return (
    <Pressable
      testID={testID}
      onPress={onPress}
      style={({ pressed }) => [{
        flexDirection: "row", alignItems: "center", gap: 12, minHeight: 56,
        paddingHorizontal: space.lg, opacity: pressed ? 0.6 : 1,
      }]}
    >
      <View style={{
        width: 32, height: 32, borderRadius: 16,
        backgroundColor: danger ? colors.surface : colors.primarySoft,
        alignItems: "center", justifyContent: "center",
      }}>
        <Ionicons name={icon} size={16} color={danger ? colors.danger : colors.primary} />
      </View>
      <Text style={{ flex: 1, color: danger ? colors.danger : colors.ink, fontFamily: fonts.bodyMedium, fontSize: 14 }}>{label}</Text>
      {value ? <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 13 }}>{value}</Text> : null}
      {onPress ? <Ionicons name="chevron-forward" size={16} color={danger ? colors.danger : colors.faint} /> : null}
    </Pressable>
  );
}
