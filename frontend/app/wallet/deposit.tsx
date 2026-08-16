import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import { Alert, Pressable, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Animated, { FadeInDown } from "react-native-reanimated";

import { api, newIdempotencyKey } from "@/src/api";
import { Btn } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useRequireAuth } from "@/src/hooks/use-require-auth";
import { radius, space, type, useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

export default function Deposit() {
  const { colors } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  useRequireAuth();

  const [amount, setAmount] = useState("");
  const [loading, setLoading] = useState(false);
  const [unavailable, setUnavailable] = useState(false);

  const submit = async () => {
    const value = Number(amount.replace(",", "."));
    if (!value || value <= 0) return;
    setLoading(true);
    try {
      await api.post("/wallet/deposits", { amount: value, method: "pix" }, { "Idempotency-Key": newIdempotencyKey() });
      Alert.alert("Depósito iniciado", "Assim que confirmado, o valor entra na sua carteira.");
      router.back();
    } catch (e: any) {
      if (e.message?.includes("não está disponível") || e.message?.includes("configurado")) {
        setUnavailable(true);
      } else {
        Alert.alert("Não foi possível depositar", e.message || "Tente novamente.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + space.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: space.xl, height: 48, gap: space.md }}>
        <Pressable testID="deposit-back-button" onPress={() => safeBack(router, "/wallet")} hitSlop={10}>
          <Ionicons name="arrow-back" size={24} color={colors.ink} />
        </Pressable>
        <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 17, flex: 1 }}>Depositar</Text>
      </View>

      <View style={{ flex: 1, padding: space.xl, justifyContent: "center" }}>
        {unavailable ? (
          <Animated.View entering={FadeInDown.duration(220)} style={{ alignItems: "center", gap: space.lg }}>
            <View style={{ width: 64, height: 64, borderRadius: 32, backgroundColor: colors.accentSoft, alignItems: "center", justifyContent: "center" }}>
              <Ionicons name="time-outline" size={28} color={colors.accent} />
            </View>
            <Text style={{ color: colors.ink, ...type.h1, textAlign: "center" }}>Depósito ainda não disponível</Text>
            <Text style={{ color: colors.muted, ...type.body, textAlign: "center" }}>
              Estamos preparando o pagamento por Pix. Por enquanto, fale com a equipe FAZÊ se precisar de saldo de teste.
            </Text>
            <Btn title="Voltar" variant="secondary" onPress={() => router.back()} />
          </Animated.View>
        ) : (
          <View style={{ gap: space.lg }}>
            <Text style={{ color: colors.ink, ...type.h1 }}>Quanto você quer depositar?</Text>
            <Text style={{ color: colors.muted, ...type.body }}>Via Pix. O saldo entra assim que o pagamento for confirmado.</Text>
            <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm, marginVertical: space.md }}>
              <Text style={{ color: colors.muted, fontSize: 26, fontFamily: fonts.bodyBold }}>R$</Text>
              <TextInput
                testID="deposit-amount-input"
                value={amount}
                onChangeText={(v) => setAmount(v.replace(/[^0-9,]/g, ""))}
                keyboardType="numeric"
                placeholder="0"
                placeholderTextColor={colors.faint}
                autoFocus
                style={{ fontSize: 44, fontFamily: fonts.headingExtraBold, color: colors.ink, minWidth: 120 }}
              />
            </View>
            <Btn testID="deposit-submit-button" title={loading ? "Processando..." : "Continuar"} onPress={submit} disabled={!Number(amount.replace(",", ".")) || loading} loading={loading} />
          </View>
        )}
      </View>
    </View>
  );
}
