import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useEffect, useState } from "react";
import { Alert, Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Animated, { FadeInDown, ZoomIn } from "react-native-reanimated";

import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { OtpInput } from "@/src/components/OtpInput";
import { Btn } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useCountdown } from "@/src/hooks/use-countdown";
import { space, type, useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

const RESEND_SECONDS = 30;

export default function VerifyPhone() {
  const { colors } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user, refreshUser } = useAuth();
  const { remaining, restart } = useCountdown();

  const [code, setCode] = useState("");
  const [error, setError] = useState(false);
  const [sending, setSending] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [devCode, setDevCode] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [noPhone, setNoPhone] = useState(false);

  const sendCode = async () => {
    setSending(true);
    try {
      const res = await api.post("/auth/send-phone-verification");
      setDevCode(res.dev_code || null);
      restart(RESEND_SECONDS);
    } catch (e: any) {
      if (/telefone antes de verificar/i.test(e.message || "")) {
        setNoPhone(true);
      } else {
        Alert.alert("Não foi possível enviar o código", e.message || "Tente novamente.");
      }
    } finally {
      setSending(false);
    }
  };

  useEffect(() => { sendCode(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const verify = async (fullCode: string) => {
    setVerifying(true);
    try {
      await api.post("/auth/verify-phone", { code: fullCode });
      await refreshUser();
      setDone(true);
    } catch (e: any) {
      setError(true);
      Alert.alert("Código incorreto", e.message || "Confira o código e tente novamente.");
    } finally {
      setVerifying(false);
    }
  };

  if (user?.verified_phone && !done) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", padding: space.xl, gap: space.lg }}>
        <Ionicons name="checkmark-circle" size={48} color={colors.green} />
        <Text style={{ color: colors.ink, ...type.h1, textAlign: "center" }}>Seu telefone já está verificado.</Text>
        <Btn testID="verify-phone-back-home" title="Voltar" onPress={() => safeBack(router, "/(tabs)/home")} />
      </View>
    );
  }

  if (noPhone) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", padding: space.xl, gap: space.lg }}>
        <Ionicons name="call-outline" size={48} color={colors.muted} />
        <Text style={{ color: colors.ink, ...type.h1, textAlign: "center" }}>Cadastre um telefone primeiro</Text>
        <Text style={{ color: colors.muted, ...type.body, textAlign: "center" }}>Você ainda não tem um telefone cadastrado. Adicione um em Segurança para poder verificar.</Text>
        <Btn testID="verify-phone-go-security" title="Ir para Segurança" onPress={() => router.replace("/security")} />
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + space.md, paddingBottom: Math.max(insets.bottom, space.xl), paddingHorizontal: space.xl }}>
      <Pressable testID="verify-phone-back-button" onPress={() => safeBack(router, "/(tabs)/home")} hitSlop={10} style={{ width: 36, height: 36, alignItems: "center", justifyContent: "center", marginLeft: -8 }}>
        <Ionicons name="arrow-back" size={22} color={colors.ink} />
      </Pressable>

      <View style={{ flex: 1, justifyContent: "center", maxWidth: 420, width: "100%", alignSelf: "center" }}>
        {done ? (
          <Animated.View entering={ZoomIn.duration(320)} style={{ alignItems: "center", gap: space.lg }}>
            <View style={{ width: 72, height: 72, borderRadius: 36, backgroundColor: colors.greenSoft, alignItems: "center", justifyContent: "center" }}>
              <Ionicons name="checkmark" size={36} color={colors.green} />
            </View>
            <Text style={{ color: colors.ink, ...type.h1, textAlign: "center" }}>Telefone verificado.</Text>
            <Btn testID="verify-phone-done-button" title="Continuar" onPress={() => safeBack(router, "/(tabs)/home")} />
          </Animated.View>
        ) : (
          <Animated.View entering={FadeInDown.duration(260)} style={{ gap: space.lg, alignItems: "center" }}>
            <Text style={{ color: colors.ink, ...type.h1, textAlign: "center" }}>Confira seu telefone</Text>
            <Text style={{ color: colors.muted, ...type.body, textAlign: "center" }}>Enviamos um código de 6 dígitos por SMS{"\n"}para o telefone da sua conta</Text>
            {devCode && (
              <View style={{ backgroundColor: colors.accentSoft, borderRadius: 12, paddingVertical: space.sm, paddingHorizontal: space.md }}>
                <Text style={{ color: colors.ink, ...type.small, textAlign: "center" }}>Modo de desenvolvimento — código: <Text style={{ fontFamily: fonts.headingExtraBold }}>{devCode}</Text></Text>
              </View>
            )}
            <OtpInput value={code} onChange={(v) => { setCode(v); setError(false); }} onComplete={verify} error={error} autoFocus />
            {verifying && <Text style={{ color: colors.muted, ...type.small }}>Verificando...</Text>}
            <Pressable testID="verify-phone-resend-button" disabled={remaining > 0 || sending} onPress={sendCode} hitSlop={8}>
              <Text style={{ color: remaining > 0 ? colors.faint : colors.primary, fontFamily: fonts.bodySemiBold, fontSize: 13 }}>
                {remaining > 0 ? `Reenviar em ${remaining}s` : "Reenviar código"}
              </Text>
            </Pressable>
          </Animated.View>
        )}
      </View>
    </View>
  );
}
