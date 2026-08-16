import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Animated, { FadeInDown } from "react-native-reanimated";

import { api, Wallet, WalletTransaction } from "@/src/api";
import { Skeleton } from "@/src/components/ui";
import { TransactionRow } from "@/src/components/WalletComponents";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useRequireAuth } from "@/src/hooks/use-require-auth";
import { radius, space, type, useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

export default function WalletHome() {
  const { colors } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  useRequireAuth();

  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [recent, setRecent] = useState<WalletTransaction[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [w, txns] = await Promise.all([api.get("/wallet"), api.get("/wallet/transactions?limit=5")]);
      setWallet(w);
      setRecent(txns);
    } catch { /* keep last known state, EmptyState covers first load */ } finally { setLoading(false); }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + space.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: space.xl, height: 48, gap: space.md }}>
        <Pressable testID="wallet-back-button" onPress={() => safeBack(router, "/(tabs)/profile")} hitSlop={10}>
          <Ionicons name="arrow-back" size={24} color={colors.ink} />
        </Pressable>
        <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 17, flex: 1 }}>Minha carteira</Text>
      </View>

      <ScrollView contentContainerStyle={{ padding: space.xl, paddingBottom: space.xxxl, gap: space.xl }} showsVerticalScrollIndicator={false}>
        {loading || !wallet ? (
          <View style={{ gap: space.md }}><Skeleton height={140} /><Skeleton height={80} /></View>
        ) : (
          <>
            <Animated.View entering={FadeInDown.duration(260)} style={{ backgroundColor: colors.primary, borderRadius: radius.xl, padding: space.xl, gap: space.xs }}>
              <Text style={{ color: "rgba(255,255,255,0.72)", ...type.micro }}>Disponível</Text>
              <Text style={{ color: "#FFFFFF", fontFamily: fonts.headingExtraBold, fontSize: 40, letterSpacing: -1 }}>
                R$ {wallet.available.toFixed(2).replace(".", ",")}
              </Text>
              <View style={{ flexDirection: "row", gap: space.xl, marginTop: space.sm }}>
                <View>
                  <Text style={{ color: "rgba(255,255,255,0.6)", ...type.micro }}>Pendente</Text>
                  <Text style={{ color: "#FFFFFF", fontFamily: fonts.bodyBold, fontSize: 15 }}>R$ {wallet.pending.toFixed(2).replace(".", ",")}</Text>
                </View>
                <View>
                  <Text style={{ color: "rgba(255,255,255,0.6)", ...type.micro }}>Em processamento</Text>
                  <Text style={{ color: "#FFFFFF", fontFamily: fonts.bodyBold, fontSize: 15 }}>R$ {wallet.processing.toFixed(2).replace(".", ",")}</Text>
                </View>
              </View>
            </Animated.View>

            <View style={{ flexDirection: "row", gap: space.sm }}>
              <ActionButton testID="wallet-deposit-button" icon="add-circle-outline" label="Depositar" onPress={() => router.push("/wallet/deposit")} />
              <ActionButton testID="wallet-withdraw-button" icon="arrow-up-circle-outline" label="Sacar" onPress={() => router.push("/wallet/withdraw")} />
              <ActionButton testID="wallet-earnings-button" icon="trending-up-outline" label="Ganhos" onPress={() => router.push("/wallet/earnings")} />
              <ActionButton testID="wallet-extract-button" icon="receipt-outline" label="Extrato" onPress={() => router.push("/wallet/extract")} />
            </View>

            <Pressable testID="wallet-bank-accounts-row" onPress={() => router.push("/wallet/bank-accounts")}
              style={{ flexDirection: "row", alignItems: "center", gap: space.md, padding: space.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md }}>
              <Ionicons name="card-outline" size={20} color={colors.primary} />
              <Text style={{ flex: 1, color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 14 }}>Contas para saque</Text>
              <Ionicons name="chevron-forward" size={18} color={colors.faint} />
            </Pressable>

            <View>
              <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: space.md }}>
                <Text style={{ color: colors.ink, ...type.h2 }}>Movimentações recentes</Text>
                <Pressable onPress={() => router.push("/wallet/extract")} hitSlop={8}>
                  <Text style={{ color: colors.primary, fontFamily: fonts.bodyBold, fontSize: 13 }}>Ver tudo</Text>
                </Pressable>
              </View>
              {recent.length === 0 ? (
                <Text style={{ color: colors.faint, fontSize: 13 }}>Nenhuma movimentação ainda.</Text>
              ) : (
                <View style={{ gap: space.sm }}>
                  {recent.map((t) => <TransactionRow key={t.id} txn={t} />)}
                </View>
              )}
            </View>
          </>
        )}
      </ScrollView>
    </View>
  );
}

function ActionButton({ icon, label, onPress, testID }: { icon: keyof typeof Ionicons.glyphMap; label: string; onPress: () => void; testID?: string }) {
  const { colors } = useTheme();
  return (
    <Pressable testID={testID} onPress={onPress} style={{ flex: 1, alignItems: "center", gap: 6, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingVertical: space.md }}>
      <Ionicons name={icon} size={20} color={colors.primary} />
      <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 11, textAlign: "center" }}>{label}</Text>
    </Pressable>
  );
}
