import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useApp } from "@/src/state";
import { Row } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useRequireAuth } from "@/src/hooks/use-require-auth";
import { radius, space, useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

export default function Security() {
  const { colors } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { me } = useApp();
  useRequireAuth();

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
            <StatusRow icon="mail-outline" label="E-mail verificado" ok={me.verified_email} />
            <Divider />
            <StatusRow icon="call-outline" label="Telefone verificado" ok={me.verified_phone} />
            <Divider />
            <StatusRow icon="shield-checkmark-outline" label="Identidade verificada" ok={me.verified_identity} />
          </View>
        </View>

        <View>
          <SectionTitle title="Acesso" />
          <View style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, overflow: "hidden" }}>
            <Row icon="lock-closed-outline" label="Alterar senha" onPress={() => router.push("/(tabs)/profile")} />
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
      </ScrollView>
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

function StatusRow({ icon, label, ok }: { icon: keyof typeof Ionicons.glyphMap; label: string; ok?: boolean }) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: space.md, paddingHorizontal: space.lg, height: 52 }}>
      <Ionicons name={icon} size={19} color={colors.muted} />
      <Text style={{ flex: 1, color: colors.ink, fontFamily: fonts.body, fontSize: 14 }}>{label}</Text>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
        <Ionicons name={ok ? "checkmark-circle" : "close-circle-outline"} size={16} color={ok ? colors.green : colors.faint} />
        <Text style={{ color: ok ? colors.green : colors.faint, fontFamily: fonts.bodySemiBold, fontSize: 12 }}>{ok ? "Verificado" : "Pendente"}</Text>
      </View>
    </View>
  );
}
