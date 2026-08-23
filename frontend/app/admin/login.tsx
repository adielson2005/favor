import React, { useState } from "react";
import { Alert, Text, View } from "react-native";

import { useAdminAuth } from "@/src/admin-auth";
import { Btn, Field } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { space, type, useTheme } from "@/src/theme";

export default function AdminLogin() {
  const { colors } = useTheme();
  const { login } = useAdminAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [needsTotp, setNeedsTotp] = useState(false);
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (!email.trim() || !password) return;
    setLoading(true);
    try {
      await login(email, password, totpCode || undefined);
    } catch (e: any) {
      const msg = e.message || "";
      if (/dois fatores/i.test(msg)) {
        setNeedsTotp(true);
        if (totpCode) Alert.alert("Código inválido", "Confira o código do seu app autenticador.");
      } else {
        Alert.alert("Não foi possível entrar", msg || "Confira o e-mail e a senha.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", padding: space.xxxl }}>
      <View style={{ width: "100%", maxWidth: 380, gap: space.lg }}>
        <View style={{ alignItems: "center", marginBottom: space.sm, gap: space.sm }}>
          <View style={{ width: 44, height: 44, borderRadius: 14, backgroundColor: colors.ink, alignItems: "center", justifyContent: "center" }}>
            <Text style={{ color: colors.bg, fontFamily: fonts.headingExtraBold, fontSize: 19 }}>f</Text>
          </View>
          <Text style={{ color: colors.ink, ...type.h1 }}>fazum admin</Text>
          <Text style={{ color: colors.muted, ...type.body, textAlign: "center" }}>Painel administrativo — acesso restrito à equipe.</Text>
        </View>
        <View style={{ backgroundColor: colors.surface, borderRadius: 20, borderWidth: 1, borderColor: colors.border, padding: space.xl, gap: space.md }}>
          <Field testID="admin-login-email-input" label="E-mail" value={email} onChangeText={setEmail} placeholder="voce@fazum.com" autoCapitalize="none" keyboardType="email-address" />
          <Field testID="admin-login-password-input" label="Senha" value={password} onChangeText={setPassword} placeholder="••••••••" secureTextEntry />
          {needsTotp && (
            <Field testID="admin-login-totp-input" label="Código de autenticação (2FA)" value={totpCode} onChangeText={setTotpCode} placeholder="000000" keyboardType="number-pad" autoFocus />
          )}
          <Btn testID="admin-login-submit" title={loading ? "Entrando..." : "Entrar"} onPress={submit} disabled={!email.trim() || !password || (needsTotp && !totpCode)} loading={loading} />
        </View>
        <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 12, textAlign: "center" }}>
          Este login é separado da sua conta fazum. Fale com um administrador principal se precisar de acesso.
        </Text>
      </View>
    </View>
  );
}
