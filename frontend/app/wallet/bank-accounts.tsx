import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { Alert, Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, BankAccount } from "@/src/api";
import { Btn, EmptyState, Field, Sheet, Skeleton } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useRequireAuth } from "@/src/hooks/use-require-auth";
import { radius, space, type, useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

export default function BankAccounts() {
  const { colors } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  useRequireAuth();

  const [accounts, setAccounts] = useState<BankAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const [holderName, setHolderName] = useState("");
  const [document, setDocument] = useState("");
  const [bankCode, setBankCode] = useState("");
  const [agency, setAgency] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [password, setPassword] = useState("");

  const load = useCallback(async () => {
    try { setAccounts(await api.get("/bank-accounts")); } catch { /* keep last */ } finally { setLoading(false); }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const resetForm = () => { setHolderName(""); setDocument(""); setBankCode(""); setAgency(""); setAccountNumber(""); setPassword(""); };

  const addAccount = async () => {
    setSaving(true);
    try {
      await api.post("/bank-accounts", {
        holder_name: holderName.trim(), document: document.replace(/\D/g, ""), bank_code: bankCode.trim(),
        agency: agency.trim(), account_number: accountNumber.trim(), account_type: "checking", password,
      });
      resetForm();
      setAddOpen(false);
      load();
    } catch (e: any) {
      Alert.alert("Não foi possível adicionar", e.message || "Confira os dados e sua senha.");
    } finally { setSaving(false); }
  };

  const setPrimary = async (id: string) => {
    try { await api.patch(`/bank-accounts/${id}/primary`, {}); load(); } catch { Alert.alert("Ops", "Não conseguimos definir como principal."); }
  };

  const confirmRemove = (account: BankAccount) => {
    Alert.alert("Remover conta", `Remover a conta terminada em ${account.account_number_masked.slice(-4)}? Essa ação é definitiva.`, [
      { text: "Cancelar", style: "cancel" },
      { text: "Remover", style: "destructive", onPress: () => promptPasswordAndRemove(account.id) },
    ]);
  };

  const [removeTarget, setRemoveTarget] = useState<string | null>(null);
  const [removePassword, setRemovePassword] = useState("");

  const promptPasswordAndRemove = (id: string) => {
    setRemoveTarget(id);
    setRemovePassword("");
  };

  const doRemove = async () => {
    if (!removeTarget) return;
    setSaving(true);
    try {
      await api.del(`/bank-accounts/${removeTarget}`, { password: removePassword });
      setRemoveTarget(null);
      load();
    } catch (e: any) {
      Alert.alert("Não foi possível remover", e.message || "Senha incorreta.");
    } finally { setSaving(false); }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + space.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: space.xl, height: 48, gap: space.md }}>
        <Pressable testID="bank-accounts-back-button" onPress={() => safeBack(router, "/wallet")} hitSlop={10}>
          <Ionicons name="arrow-back" size={24} color={colors.ink} />
        </Pressable>
        <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 17, flex: 1 }}>Contas para saque</Text>
        <Pressable testID="add-bank-account-button" onPress={() => setAddOpen(true)} hitSlop={8}>
          <Ionicons name="add-circle" size={26} color={colors.primary} />
        </Pressable>
      </View>

      <ScrollView contentContainerStyle={{ padding: space.xl, gap: space.md }}>
        {loading ? <Skeleton height={80} /> : accounts.length === 0 ? (
          <EmptyState icon="card-outline" title="Nenhuma conta cadastrada." body="Adicione uma conta bancária para poder sacar seus ganhos." actionTitle="Adicionar conta" onAction={() => setAddOpen(true)} />
        ) : accounts.map((acc) => (
          <View key={acc.id} style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: space.lg, gap: space.sm }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
              <Ionicons name="card-outline" size={18} color={colors.primary} />
              <Text style={{ flex: 1, color: colors.ink, fontFamily: fonts.bodyBold, fontSize: 14 }}>{acc.holder_name}</Text>
              {acc.is_primary && <View style={{ backgroundColor: colors.primarySoft, paddingHorizontal: space.sm, paddingVertical: 3, borderRadius: radius.pill }}><Text style={{ color: colors.primary, fontSize: 11, fontFamily: fonts.bodyBold }}>Principal</Text></View>}
            </View>
            <Text style={{ color: colors.muted, fontSize: 13 }}>Banco {acc.bank_code} · Ag {acc.agency} · Conta {acc.account_number_masked}</Text>
            <Text style={{ color: colors.faint, fontSize: 12 }}>{acc.document_masked}</Text>
            <View style={{ flexDirection: "row", gap: space.sm, marginTop: space.xs }}>
              {!acc.is_primary && <Pressable onPress={() => setPrimary(acc.id)} hitSlop={6}><Text style={{ color: colors.primary, fontFamily: fonts.bodyBold, fontSize: 13 }}>Definir como principal</Text></Pressable>}
              <Pressable onPress={() => confirmRemove(acc)} hitSlop={6}><Text style={{ color: colors.danger, fontFamily: fonts.bodyBold, fontSize: 13 }}>Remover</Text></Pressable>
            </View>
          </View>
        ))}
      </ScrollView>

      <Sheet visible={addOpen} onClose={() => setAddOpen(false)} title="Adicionar conta">
        <View style={{ gap: space.md, paddingVertical: space.md, paddingBottom: space.xxl }}>
          <Field label="Nome do titular" value={holderName} onChangeText={setHolderName} testID="bank-holder-input" />
          <Field label="CPF ou CNPJ" value={document} onChangeText={setDocument} keyboardType="numeric" testID="bank-document-input" />
          <View style={{ flexDirection: "row", gap: space.sm }}>
            <View style={{ flex: 1 }}><Field label="Banco" value={bankCode} onChangeText={setBankCode} placeholder="001" testID="bank-code-input" /></View>
            <View style={{ flex: 1 }}><Field label="Agência" value={agency} onChangeText={setAgency} testID="bank-agency-input" /></View>
          </View>
          <Field label="Conta" value={accountNumber} onChangeText={setAccountNumber} testID="bank-account-number-input" />
          <Field label="Confirme sua senha" value={password} onChangeText={setPassword} secureTextEntry testID="bank-password-input" />
          <Btn testID="save-bank-account-button" title="Adicionar" onPress={addAccount} loading={saving}
            disabled={!holderName.trim() || !document.trim() || !bankCode.trim() || !agency.trim() || !accountNumber.trim() || !password} />
        </View>
      </Sheet>

      <Sheet visible={!!removeTarget} onClose={() => setRemoveTarget(null)} title="Confirmar senha">
        <View style={{ gap: space.md, paddingVertical: space.md, paddingBottom: space.xxl }}>
          <Text style={{ color: colors.muted, ...type.body }}>Por segurança, confirme sua senha para remover esta conta.</Text>
          <Field label="Senha" value={removePassword} onChangeText={setRemovePassword} secureTextEntry testID="remove-bank-password-input" autoFocus />
          <Btn testID="confirm-remove-bank-button" title="Remover conta" variant="danger" onPress={doRemove} loading={saving} disabled={!removePassword} />
        </View>
      </Sheet>
    </View>
  );
}
