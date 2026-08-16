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

export default function VerifyEmail() {
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

  const sendCode = async () => {
    setSending(true);
    try {
      const res = await api.post("/auth/send-verification");
      setDevCode(res.dev_code || null);
      restart(RESEND_SECONDS);
    } catch (e: any) {
      Alert.alert("Não foi possível enviar o código", e.message || "Tente novamente.");
    } finally {
      setSending(false);
    }
  };

  useEffect(() => { sendCode(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const verify = async (fullCode: string) => {
    setVerifying(true);
    try {
      await api.post("/auth/verify-email", { code: fullCode });
      await refreshUser();
      setDone(true);
    } catch (e: any) {
      setError(true);
      Alert.alert("Código incorreto", e.message || "Confira o código e tente novamente.");
    } finally {
      setVerifying(false);
    }
  };

  if (user?.verified_email && !done) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", padding: space.xl, gap: space.lg }}>
        <Ionicons name="checkmark-circle" size={48} color={colors.green} />
        <Text style={{ color: colors.ink, ...type.h1, textAlign: "center" }}>Seu e-mail já está verificado.</Text>
        <Btn testID="verify-back-home" title="Voltar" onPress={() => safeBack(router, "/(tabs)/home")} />
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + space.md, paddingBottom: Math.max(insets.bottom, space.xl), paddingHorizontal: space.xl }}>
      <Pressable testID="verify-back-button" onPress={() => safeBack(router, "/(tabs)/home")} hitSlop={10} style={{ width: 36, height: 36, alignItems: "center", justifyContent: "center", marginLeft: -8 }}>
        <Ionicons name="arrow-back" size={22} color={colors.ink} />
      </Pressable>

      <View style={{ flex: 1, justifyContent: "center", maxWidth: 420, width: "100%", alignSelf: "center" }}>
        {done ? (
          <Animated.View entering={ZoomIn.duration(320)} style={{ alignItems: "center", gap: space.lg }}>
            <View style={{ width: 72, height: 72, borderRadius: 36, backgroundColor: colors.greenSoft, alignItems: "center", justifyContent: "center" }}>
              <Ionicons name="checkmark" size={36} color={colors.green} />
            </View>
            <Text style={{ color: colors.ink, ...type.h1, textAlign: "center" }}>E-mail verificado.</Text>
            <Btn testID="verify-done-button" title="Continuar" onPress={() => safeBack(router, "/(tabs)/home")} />
          </Animated.View>
        ) : (
          <Animated.View entering={FadeInDown.duration(260)} style={{ gap: space.lg, alignItems: "center" }}>
            <Text style={{ color: colors.ink, ...type.h1, textAlign: "center" }}>Confira seu e-mail</Text>
            <Text style={{ color: colors.muted, ...type.body, textAlign: "center" }}>Enviamos um código de 6 dígitos para{"\n"}{user?.name ? "sua conta" : "seu e-mail"}</Text>
            {devCode && (
              <View style={{ backgroundColor: colors.accentSoft, borderRadius: 12, paddingVertical: space.sm, paddingHorizontal: space.md }}>
                <Text style={{ color: colors.ink, ...type.small, textAlign: "center" }}>Modo de desenvolvimento — código: <Text style={{ fontFamily: fonts.headingExtraBold }}>{devCode}</Text></Text>
              </View>
            )}
            <OtpInput value={code} onChange={(v) => { setCode(v); setError(false); }} onComplete={verify} error={error} autoFocus />
            {verifying && <Text style={{ color: colors.muted, ...type.small }}>Verificando...</Text>}
            <Pressable testID="verify-resend-button" disabled={remaining > 0 || sending} onPress={sendCode} hitSlop={8}>
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
