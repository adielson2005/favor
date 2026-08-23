import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, Alert, Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Animated, { FadeInDown, ZoomIn } from "react-native-reanimated";

import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { OtpInput } from "@/src/components/OtpInput";
import { Btn, Field } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useCountdown } from "@/src/hooks/use-countdown";
import { space, type, useTheme } from "@/src/theme";

const RESEND_SECONDS = 30;

function formatPhoneBR(raw: string): string {
  const digits = raw.replace(/\D/g, "").slice(0, 11);
  if (digits.length <= 2) return digits;
  if (digits.length <= 7) return `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
  return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
}

function isValidPhoneBR(formatted: string): boolean {
  const digits = formatted.replace(/\D/g, "");
  return digits.length === 10 || digits.length === 11;
}

// Reached right after a Google sign-in/sign-up when the account is still missing
// info our own verification layer requires (today, just phone — Google verifying an
// e-mail never substitutes FAZUM's own phone OTP). Never creates a second account:
// this only ever edits the already-authenticated user from loginWithGoogle.
export default function CompleteProfile() {
  const { colors } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user, refreshUser } = useAuth();
  const { remaining, restart } = useCountdown();

  const needsPhone = !user?.phone;
  const [stage, setStage] = useState<"phone" | "otp" | "done">(needsPhone ? "phone" : "otp");
  const [phone, setPhone] = useState("");
  const [submittingPhone, setSubmittingPhone] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [sending, setSending] = useState(false);
  const [devCode, setDevCode] = useState<string | null>(null);

  useEffect(() => {
    if (user?.verified_phone) router.replace("/");
  }, [user?.verified_phone, router]);

  const sendCode = async () => {
    setSending(true);
    try {
      const res = await api.post("/auth/send-phone-verification");
      setDevCode(res.dev_code || null);
      restart(RESEND_SECONDS);
    } catch (e: any) {
      Alert.alert("Não foi possível enviar o código", e.message || "Tente novamente.");
    } finally {
      setSending(false);
    }
  };

  // Only auto-send when we land directly on the OTP stage (phone already existed,
  // just unverified) — the phone stage's own submit already triggers the first send.
  useEffect(() => {
    if (!needsPhone) sendCode();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const submitPhone = async () => {
    setSubmittingPhone(true);
    try {
      const res = await api.post("/auth/change-phone", { phone: phone.replace(/\D/g, "") });
      setDevCode(res.dev_code || null);
      restart(RESEND_SECONDS);
      await refreshUser();
      setStage("otp");
    } catch (e: any) {
      Alert.alert("Não foi possível salvar seu telefone", e.message || "Tente novamente.");
    } finally {
      setSubmittingPhone(false);
    }
  };

  const verify = async (fullCode: string) => {
    setVerifying(true);
    try {
      await api.post("/auth/verify-phone", { code: fullCode });
      await refreshUser();
      setStage("done");
    } catch (e: any) {
      setError(true);
      Alert.alert("Código incorreto", e.message || "Confira o código e tente novamente.");
    } finally {
      setVerifying(false);
    }
  };

  useEffect(() => {
    if (stage !== "done") return;
    const t = setTimeout(() => router.replace("/"), 1400);
    return () => clearTimeout(t);
  }, [stage, router]);

  if (!user) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  const hint = { color: colors.muted, ...type.body, marginBottom: space.xl };

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + space.xl, paddingBottom: Math.max(insets.bottom, space.xl), paddingHorizontal: space.xl }}>
      <View style={{ flex: 1, justifyContent: "center", maxWidth: 420, width: "100%", alignSelf: "center" }}>
        {stage === "phone" && (
          <Animated.View entering={FadeInDown.duration(240)} style={{ gap: space.lg }}>
            <Text style={{ color: colors.ink, ...type.display, fontSize: 26 }}>Quase pronto!</Text>
            <Text style={hint}>
              Sua conta Google já confirma seu e-mail, mas o fazum também precisa do seu telefone para proteger seus pedidos e pagamentos.
            </Text>
            <Field
              testID="complete-profile-phone-input"
              label="Telefone"
              value={phone}
              onChangeText={(v) => setPhone(formatPhoneBR(v))}
              placeholder="(94) 99999-9999"
              keyboardType="phone-pad"
              autoComplete="tel"
              autoFocus
            />
            <Btn
              testID="complete-profile-phone-continue"
              title={submittingPhone ? "Salvando..." : "Continuar"}
              icon="arrow-forward"
              onPress={submitPhone}
              disabled={!isValidPhoneBR(phone) || submittingPhone}
              loading={submittingPhone}
            />
          </Animated.View>
        )}

        {stage === "otp" && (
          <Animated.View entering={FadeInDown.duration(260)} style={{ gap: space.lg, alignItems: "center" }}>
            <Text style={{ color: colors.ink, ...type.h1, textAlign: "center" }}>Confira seu telefone</Text>
            <Text style={{ color: colors.muted, ...type.body, textAlign: "center" }}>
              Enviamos um código de 6 dígitos por SMS{"\n"}para o telefone da sua conta
            </Text>
            {devCode && (
              <View style={{ backgroundColor: colors.accentSoft, borderRadius: 12, paddingVertical: space.sm, paddingHorizontal: space.md }}>
                <Text style={{ color: colors.ink, ...type.small, textAlign: "center" }}>
                  Modo de desenvolvimento — código: <Text style={{ fontFamily: fonts.headingExtraBold }}>{devCode}</Text>
                </Text>
              </View>
            )}
            <OtpInput value={code} onChange={(v) => { setCode(v); setError(false); }} onComplete={verify} error={error} autoFocus />
            {verifying && <Text style={{ color: colors.muted, ...type.small }}>Verificando...</Text>}
            <Pressable testID="complete-profile-resend-button" disabled={remaining > 0 || sending} onPress={sendCode} hitSlop={8}>
              <Text style={{ color: remaining > 0 ? colors.faint : colors.primary, fontFamily: fonts.bodySemiBold, fontSize: 13 }}>
                {remaining > 0 ? `Reenviar em ${remaining}s` : "Reenviar código"}
              </Text>
            </Pressable>
          </Animated.View>
        )}

        {stage === "done" && (
          <Animated.View entering={ZoomIn.duration(320)} style={{ alignItems: "center", gap: space.lg }}>
            <View style={{ width: 72, height: 72, borderRadius: 36, backgroundColor: colors.greenSoft, alignItems: "center", justifyContent: "center" }}>
              <Ionicons name="checkmark" size={36} color={colors.green} />
            </View>
            <Text style={{ color: colors.ink, ...type.h1, textAlign: "center" }}>Cadastro concluído.</Text>
          </Animated.View>
        )}
      </View>
    </View>
  );
}
