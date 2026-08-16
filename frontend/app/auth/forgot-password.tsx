import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import { Alert, Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Animated, { FadeIn, FadeInDown, ZoomIn } from "react-native-reanimated";

import { api } from "@/src/api";
import { OtpInput } from "@/src/components/OtpInput";
import { Btn, Field } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useCountdown } from "@/src/hooks/use-countdown";
import { space, type, useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

const RESEND_SECONDS = 30;
type Step = "email" | "code" | "password" | "done";

export default function ForgotPassword() {
  const { colors } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { remaining, restart } = useCountdown();

  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [codeError, setCodeError] = useState(false);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [devCode, setDevCode] = useState<string | null>(null);

  const sendCode = async () => {
    setLoading(true);
    try {
      const res = await api.post("/auth/forgot-password", { email: email.trim().toLowerCase() });
      setDevCode(res.dev_code || null);
      restart(RESEND_SECONDS);
      setStep("code");
    } catch (e: any) {
      Alert.alert("Não foi possível enviar o código", e.message || "Tente novamente.");
    } finally {
      setLoading(false);
    }
  };

  const onCodeComplete = () => {
    setCodeError(false);
    setStep("password");
  };

  const resetPassword = async () => {
    if (password.length < 8) { Alert.alert("Senha muito curta", "Use pelo menos 8 caracteres."); return; }
    if (password !== confirm) { Alert.alert("As senhas não coincidem", "Confira e tente de novo."); return; }
    setLoading(true);
    try {
      await api.post("/auth/reset-password", { email: email.trim().toLowerCase(), code, password });
      setStep("done");
    } catch (e: any) {
      setCodeError(true);
      setStep("code");
      Alert.alert("Não foi possível trocar a senha", e.message || "O código pode ter expirado.");
    } finally {
      setLoading(false);
    }
  };

  const back = () => {
    if (step === "email") safeBack(router, "/auth/login");
    else if (step === "code") setStep("email");
    else if (step === "password") setStep("code");
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + space.md, paddingBottom: Math.max(insets.bottom, space.xl), paddingHorizontal: space.xl }}>
      {step !== "done" && (
        <Pressable testID="forgot-back-button" onPress={back} hitSlop={10} style={{ width: 36, height: 36, alignItems: "center", justifyContent: "center", marginLeft: -8 }}>
          <Ionicons name="arrow-back" size={22} color={colors.ink} />
        </Pressable>
      )}

      <View style={{ flex: 1, justifyContent: "center", maxWidth: 420, width: "100%", alignSelf: "center" }}>
        {step === "email" && (
          <Animated.View entering={FadeInDown.duration(260)} style={{ gap: space.md }}>
            <Text style={{ color: colors.ink, ...type.h1 }}>Esqueceu sua senha?</Text>
            <Text style={{ color: colors.muted, ...type.body, marginBottom: space.sm }}>Informe o e-mail da sua conta e enviaremos um código de recuperação.</Text>
            <Field testID="forgot-email-input" label="E-mail" value={email} onChangeText={setEmail} placeholder="voce@email.com" autoCapitalize="none" keyboardType="email-address" autoFocus />
            <Btn testID="forgot-send-button" title={loading ? "Enviando..." : "Enviar código"} onPress={sendCode} disabled={!email.trim() || loading} loading={loading} />
          </Animated.View>
        )}

        {step === "code" && (
          <Animated.View entering={FadeInDown.duration(260)} style={{ gap: space.lg, alignItems: "center" }}>
            <Text style={{ color: colors.ink, ...type.h1, textAlign: "center" }}>Confirme o código</Text>
            <Text style={{ color: colors.muted, ...type.body, textAlign: "center" }}>Enviamos um código de 6 dígitos para{"\n"}{email}</Text>
            {devCode && (
              <View style={{ backgroundColor: colors.accentSoft, borderRadius: 12, paddingVertical: space.sm, paddingHorizontal: space.md }}>
                <Text style={{ color: colors.ink, ...type.small, textAlign: "center" }}>Modo de desenvolvimento — código: <Text style={{ fontFamily: fonts.headingExtraBold }}>{devCode}</Text></Text>
              </View>
            )}
            <OtpInput value={code} onChange={(v) => { setCode(v); setCodeError(false); }} onComplete={onCodeComplete} error={codeError} autoFocus />
            <Pressable testID="forgot-resend-button" disabled={remaining > 0} onPress={sendCode} hitSlop={8}>
              <Text style={{ color: remaining > 0 ? colors.faint : colors.primary, fontFamily: fonts.bodySemiBold, fontSize: 13 }}>
                {remaining > 0 ? `Reenviar em ${remaining}s` : "Reenviar código"}
              </Text>
            </Pressable>
          </Animated.View>
        )}

        {step === "password" && (
          <Animated.View entering={FadeInDown.duration(260)} style={{ gap: space.md }}>
            <Text style={{ color: colors.ink, ...type.h1 }}>Crie uma nova senha</Text>
            <Text style={{ color: colors.muted, ...type.body, marginBottom: space.sm }}>Use pelo menos 8 caracteres.</Text>
            <Field testID="forgot-password-input" label="Nova senha" value={password} onChangeText={setPassword} placeholder="••••••••" secureTextEntry autoFocus />
            <Field testID="forgot-confirm-input" label="Confirmar senha" value={confirm} onChangeText={setConfirm} placeholder="••••••••" secureTextEntry />
            <Btn testID="forgot-reset-button" title={loading ? "Salvando..." : "Salvar nova senha"} onPress={resetPassword} disabled={!password || !confirm || loading} loading={loading} />
          </Animated.View>
        )}

        {step === "done" && (
          <Animated.View entering={ZoomIn.duration(320)} style={{ alignItems: "center", gap: space.lg }}>
            <View style={{ width: 72, height: 72, borderRadius: 36, backgroundColor: colors.greenSoft, alignItems: "center", justifyContent: "center" }}>
              <Ionicons name="checkmark" size={36} color={colors.green} />
            </View>
            <Text style={{ color: colors.ink, ...type.h1, textAlign: "center" }}>Senha alterada.</Text>
            <Text style={{ color: colors.muted, ...type.body, textAlign: "center" }}>Agora é só entrar com sua nova senha.</Text>
            <Btn testID="forgot-done-login-button" title="Entrar" onPress={() => router.replace("/auth/login")} />
          </Animated.View>
        )}
      </View>
    </View>
  );
}
