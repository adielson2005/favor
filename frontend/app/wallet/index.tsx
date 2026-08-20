import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useEffect, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Animated, { FadeInDown } from "react-native-reanimated";

import { api, Wallet, WalletTransaction } from "@/src/api";
import { FazumPayMark } from "@/src/components/Logo";
import { Skeleton } from "@/src/components/ui";
import { TransactionRow } from "@/src/components/WalletComponents";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useRequireAuth } from "@/src/hooks/use-require-auth";
import { radius, space, type, useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";
import { storage } from "@/src/utils/storage";

const HIDE_BALANCE_KEY = "faze:wallet-hide-balance";

export default function WalletHome() {
  const { colors } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  useRequireAuth();

  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [recent, setRecent] = useState<WalletTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [hidden, setHidden] = useState(false);

  useEffect(() => { storage.getItem(HIDE_BALANCE_KEY, false).then((v) => setHidden(!!v)); }, []);
  const toggleHidden = () => { const next = !hidden; setHidden(next); storage.setItem(HIDE_BALANCE_KEY, next); };

  const load = useCallback(async () => {
    try {
      const [w, txns] = await Promise.all([api.get("/wallet"), api.get("/wallet/transactions?limit=5")]);
      setWallet(w);
      setRecent(txns);
    } catch { /* keep last known state, EmptyState covers first load */ } finally { setLoading(false); }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const money = (v: number) => (hidden ? "R$ ••••" : `R$ ${v.toFixed(2).replace(".", ",")}`);

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + space.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: space.xl, height: 48, gap: space.md }}>
        <Pressable testID="wallet-back-button" onPress={() => safeBack(router, "/(tabs)/profile")} hitSlop={10}>
          <Ionicons name="arrow-back" size={24} color={colors.ink} />
        </Pressable>
        <View style={{ flex: 1 }}><FazumPayMark size={22} /></View>
      </View>

      <ScrollView contentContainerStyle={{ padding: space.xl, paddingBottom: space.xxxl, gap: space.xl }} showsVerticalScrollIndicator={false}>
        {loading || !wallet ? (
          <View style={{ gap: space.md }}><Skeleton height={180} /><Skeleton height={80} /></View>
        ) : (
          <>
            <Animated.View entering={FadeInDown.duration(260)}>
              <LinearGradient
                colors={["#091323", "#0A7335"]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={{ borderRadius: radius.xl, padding: space.xl, gap: space.xs, overflow: "hidden" }}
              >
                {/* Faint decorative circles — the "fintech card" texture every one of these wallet screens uses. */}
                <View pointerEvents="none" style={{ position: "absolute", top: -40, right: -30, width: 140, height: 140, borderRadius: 70, backgroundColor: "rgba(255,255,255,0.06)" }} />
                <View pointerEvents="none" style={{ position: "absolute", bottom: -50, left: -20, width: 120, height: 120, borderRadius: 60, backgroundColor: "rgba(255,255,255,0.05)" }} />

                <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
                  <FazumPayMark size={20} light />
                  <Pressable testID="wallet-toggle-visibility" onPress={toggleHidden} hitSlop={10}>
                    <Ionicons name={hidden ? "eye-off-outline" : "eye-outline"} size={19} color="rgba(255,255,255,0.85)" />
                  </Pressable>
                </View>

                <Text style={{ color: "rgba(255,255,255,0.72)", ...type.micro, marginTop: space.md }}>Saldo disponível</Text>
                <Text style={{ color: "#FFFFFF", fontFamily: fonts.headingExtraBold, fontSize: 40, letterSpacing: -1 }}>
                  {money(wallet.available)}
                </Text>

                <View style={{ flexDirection: "row", gap: space.xl, marginTop: space.sm }}>
                  <View>
                    <Text style={{ color: "rgba(255,255,255,0.6)", ...type.micro }}>Pendente</Text>
                    <Text style={{ color: "#FFFFFF", fontFamily: fonts.bodyBold, fontSize: 15 }}>{money(wallet.pending)}</Text>
                  </View>
                  <View>
                    <Text style={{ color: "rgba(255,255,255,0.6)", ...type.micro }}>Em processamento</Text>
                    <Text style={{ color: "#FFFFFF", fontFamily: fonts.bodyBold, fontSize: 15 }}>{money(wallet.processing)}</Text>
                  </View>
                </View>
              </LinearGradient>
            </Animated.View>

            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <CircleAction testID="wallet-deposit-button" icon="add" label="Depositar" onPress={() => router.push("/wallet/deposit")} />
              <CircleAction testID="wallet-withdraw-button" icon="arrow-up" label="Sacar" onPress={() => router.push("/wallet/withdraw")} />
              <CircleAction testID="wallet-earnings-button" icon="trending-up" label="Ganhos" onPress={() => router.push("/wallet/earnings")} />
              <CircleAction testID="wallet-extract-button" icon="receipt" label="Extrato" onPress={() => router.push("/wallet/extract")} />
              <CircleAction testID="wallet-bank-accounts-button" icon="card" label="Contas" onPress={() => router.push("/wallet/bank-accounts")} />
            </View>

            <View style={{ flexDirection: "row", alignItems: "flex-start", gap: space.sm, backgroundColor: colors.alt, borderRadius: radius.md, padding: space.md }}>
              <Ionicons name="information-circle-outline" size={16} color={colors.faint} style={{ marginTop: 1 }} />
              <Text style={{ flex: 1, color: colors.faint, fontSize: 12, lineHeight: 17 }}>
                fazumPay é a carteira digital da fazum: guarde, receba e saque o que você ganha na plataforma. Ainda não é uma conta bancária.
              </Text>
            </View>

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

function CircleAction({ icon, label, onPress, testID }: { icon: keyof typeof Ionicons.glyphMap; label: string; onPress: () => void; testID?: string }) {
  const { colors } = useTheme();
  return (
    <Pressable testID={testID} onPress={onPress} style={({ pressed }) => [{ alignItems: "center", gap: 6, width: 60, opacity: pressed ? 0.7 : 1 }]}>
      <View style={{ width: 48, height: 48, borderRadius: 24, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" }}>
        <Ionicons name={icon} size={20} color={colors.primary} />
      </View>
      <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 11, textAlign: "center" }}>{label}</Text>
    </Pressable>
  );
}
