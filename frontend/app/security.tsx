import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { Alert, Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useApp } from "@/src/state";
import { Avatar, Row } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useRequireAuth } from "@/src/hooks/use-require-auth";
import { radius, space, useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

type Block = { blocked_user_id: string; user: { id: string; name: string; initials: string; avatar_b64?: string | null } | null };

export default function Security() {
  const { colors } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { me } = useApp();
  useRequireAuth();

  const [blocks, setBlocks] = useState<Block[]>([]);
  useFocusEffect(useCallback(() => { api.get("/blocks").then(setBlocks).catch(() => {}); }, []));

  const unblock = (userId: string) => {
    Alert.alert("Desbloquear usuário", "Vocês voltam a poder se contatar. Continuar?", [
      { text: "Cancelar", style: "cancel" },
      { text: "Desbloquear", onPress: async () => { try { await api.del(`/blocks/${userId}`); setBlocks((b) => b.filter((x) => x.blocked_user_id !== userId)); } catch { Alert.alert("Ops", "Não conseguimos desbloquear agora."); } } },
    ]);
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
