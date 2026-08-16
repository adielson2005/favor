import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { Alert, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Animated, { FadeInDown, ZoomIn } from "react-native-reanimated";

import { api, BankAccount, newIdempotencyKey, Wallet } from "@/src/api";
import { Btn, EmptyState, Field } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useRequireAuth } from "@/src/hooks/use-require-auth";
import { radius, space, type, useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

const STATUS_LABELS: Record<string, string> = {
  PENDING: "Em processamento", PROCESSING: "Processando", COMPLETED: "Concluído",
  FAILED: "Recusado", CANCELLED: "Cancelado", REVIEW_REQUIRED: "Em análise",
};

export default function Withdraw() {
  const { colors } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  useRequireAuth();

  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [accounts, setAccounts] = useState<BankAccount[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<string | null>(null);
  const [amount, setAmount] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState<{ status: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const [w, accs] = await Promise.all([api.get("/wallet"), api.get("/bank-accounts")]);
      setWallet(w);
      setAccounts(accs);
      const primary = accs.find((a: BankAccount) => a.is_primary) || accs[0];
      if (primary) setSelectedAccount(primary.id);
    } catch { /* keep last */ } finally { setLoading(false); }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const value = Number(amount.replace(",", "."));

  const submit = async () => {
    if (!selectedAccount || !value || !password) return;
    setSubmitting(true);
    try {
      const result = await api.post("/wallet/withdrawals", { amount: value, bank_account_id: selectedAccount, password }, { "Idempotency-Key": newIdempotencyKey() });
      setDone({ status: result.status });
    } catch (e: any) {
      Alert.alert("Não foi possível sacar", e.message || "Tente novamente.");
    } finally { setSubmitting(false); }
  };

  if (done) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", padding: space.xl, gap: space.lg }}>
        <Animated.View entering={ZoomIn.duration(320)} style={{ width: 72, height: 72, borderRadius: 36, backgroundColor: colors.greenSoft, alignItems: "center", justifyContent: "center" }}>
          <Ionicons name="checkmark" size={34} color={colors.green} />
        </Animated.View>
        <Text style={{ color: colors.ink, ...type.h1, textAlign: "center" }}>Saque solicitado.</Text>
        <Text style={{ color: colors.muted, ...type.body, textAlign: "center" }}>
          {done.status === "REVIEW_REQUIRED" ? "Seu saque está em análise por segurança e será processado em breve." : "Assim que aprovado, o valor será enviado para sua conta."}
        </Text>
        <Btn title="Voltar para a carteira" onPress={() => router.replace("/wallet")} />
      </View>
    );
  }

  if (!loading && accounts.length === 0) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + space.md }}>
        <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: space.xl, height: 48, gap: space.md }}>
          <Pressable onPress={() => safeBack(router, "/wallet")} hitSlop={10}><Ionicons name="arrow-back" size={24} color={colors.ink} /></Pressable>
          <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 17 }}>Sacar</Text>
        </View>
        <View style={{ flex: 1, padding: space.xl, justifyContent: "center" }}>
          <EmptyState icon="card-outline" title="Adicione uma conta primeiro." body="Você precisa de uma conta bancária cadastrada para sacar." actionTitle="Adicionar conta" onAction={() => router.push("/wallet/bank-accounts")} />
        </View>
      </View>
    );
  }

  const fee = 0; // no payout provider configured yet — fee stays at zero until real payout costs exist
  const total = Math.max(value - fee, 0);

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + space.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: space.xl, height: 48, gap: space.md }}>
        <Pressable testID="withdraw-back-button" onPress={() => safeBack(router, "/wallet")} hitSlop={10}>
          <Ionicons name="arrow-back" size={24} color={colors.ink} />
        </Pressable>
        <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 17, flex: 1 }}>Sacar</Text>
      </View>

      <ScrollView contentContainerStyle={{ padding: space.xl, gap: space.lg }}>
        <Animated.View entering={FadeInDown.duration(220)} style={{ gap: space.lg }}>
          <Text style={{ color: colors.muted, ...type.small }}>Disponível: R$ {(wallet?.available || 0).toFixed(2).replace(".", ",")}</Text>

          <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
            <Text style={{ color: colors.muted, fontSize: 26, fontFamily: fonts.bodyBold }}>R$</Text>
            <TextInput
              testID="withdraw-amount-input"
              value={amount}
              onChangeText={(v) => setAmount(v.replace(/[^0-9,]/g, ""))}
              keyboardType="numeric"
              placeholder="0"
              placeholderTextColor={colors.faint}
              style={{ fontSize: 40, fontFamily: fonts.headingExtraBold, color: colors.ink, minWidth: 100 }}
            />
          </View>

          <View>
            <Text style={{ color: colors.muted, ...type.micro, marginBottom: space.sm }}>Conta de destino</Text>
            <View style={{ gap: space.sm }}>
              {accounts.map((acc) => (
                <Pressable key={acc.id} testID={`withdraw-account-${acc.id}`} onPress={() => setSelectedAccount(acc.id)}
                  style={{ flexDirection: "row", alignItems: "center", gap: space.sm, padding: space.md, borderRadius: radius.md, borderWidth: 1.5, borderColor: selectedAccount === acc.id ? colors.primary : colors.border, backgroundColor: colors.surface }}>
                  <Ionicons name="card-outline" size={18} color={selectedAccount === acc.id ? colors.primary : colors.muted} />
                  <Text style={{ flex: 1, color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 13 }}>{acc.holder_name} · {acc.account_number_masked}</Text>
                  {selectedAccount === acc.id && <Ionicons name="checkmark-circle" size={18} color={colors.primary} />}
                </Pressable>
              ))}
            </View>
          </View>

          {value > 0 && (
            <View style={{ backgroundColor: colors.alt, borderRadius: radius.md, padding: space.lg, gap: space.xs }}>
              <Row label="Valor do saque" value={`R$ ${value.toFixed(2).replace(".", ",")}`} />
              <Row label="Taxa" value={`R$ ${fee.toFixed(2).replace(".", ",")}`} />
              <Row label="Você recebe" value={`R$ ${total.toFixed(2).replace(".", ",")}`} strong />
              <Text style={{ color: colors.faint, fontSize: 12, marginTop: space.xs }}>Prazo: até 2 dias úteis após aprovação.</Text>
            </View>
          )}

          <Field label="Confirme sua senha" value={password} onChangeText={setPassword} secureTextEntry testID="withdraw-password-input" />

          <Btn testID="withdraw-submit-button" title={submitting ? "Processando..." : `Sacar R$ ${value ? value.toFixed(2).replace(".", ",") : "0,00"}`}
            onPress={submit} loading={submitting} disabled={!value || !selectedAccount || !password || (wallet ? value > wallet.available : true)} />
        </Animated.View>
      </ScrollView>
    </View>
  );
}

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
      <Text style={{ color: colors.muted, fontSize: 13 }}>{label}</Text>
      <Text style={{ color: colors.ink, fontFamily: strong ? fonts.headingBold : fonts.bodySemiBold, fontSize: strong ? 16 : 13 }}>{value}</Text>
    </View>
  );
}
