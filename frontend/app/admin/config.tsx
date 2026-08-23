import React, { useEffect, useState } from "react";
import { Alert, Text, View } from "react-native";

import { adminApi } from "@/src/admin-api";
import { Badge } from "@/src/components/admin/Badge";
import { fonts } from "@/src/hooks/use-app-fonts";
import { space, useTheme } from "@/src/theme";
import { Btn, Field } from "@/src/components/ui";

export default function AdminConfig() {
  const { colors } = useTheme();
  const [commission, setCommission] = useState("");
  const [minWithdrawal, setMinWithdrawal] = useState("");
  const [maxWithdrawalDay, setMaxWithdrawalDay] = useState("");
  const [maxDeposit, setMaxDeposit] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    adminApi.get("/admin/config").then((d) => {
      setCommission(String(d.commission_percent ?? ""));
      setMinWithdrawal(String(d.min_withdrawal ?? ""));
      setMaxWithdrawalDay(String(d.max_withdrawal_per_day ?? ""));
      setMaxDeposit(String(d.max_deposit_per_transaction ?? ""));
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await adminApi.patch("/admin/config", {
        commission_percent: Number(commission), min_withdrawal: Number(minWithdrawal),
        max_withdrawal_per_day: Number(maxWithdrawalDay), max_deposit_per_transaction: Number(maxDeposit),
      });
      Alert.alert("Configuração salva", "As novas regras financeiras já estão em vigor.");
    } catch (e: any) {
      Alert.alert("Ops", e.message || "Não foi possível salvar.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return null;

  return (
    <View style={{ gap: space.md, maxWidth: 420 }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
        <Badge label="CRÍTICA" tone="danger" />
        <Text style={{ flex: 1, color: colors.faint, fontFamily: fonts.body, fontSize: 12, lineHeight: 16 }}>
          Regras financeiras. Só o administrador principal pode alterar, e cada mudança fica registrada na auditoria.
        </Text>
      </View>
      <Field label="Comissão fazum (%)" value={commission} onChangeText={setCommission} keyboardType="numeric" />
      <Field label="Saque mínimo (R$)" value={minWithdrawal} onChangeText={setMinWithdrawal} keyboardType="numeric" />
      <Field label="Limite de saque por dia (R$)" value={maxWithdrawalDay} onChangeText={setMaxWithdrawalDay} keyboardType="numeric" />
      <Field label="Limite de depósito por transação (R$)" value={maxDeposit} onChangeText={setMaxDeposit} keyboardType="numeric" />
      <Btn title="Salvar configuração" onPress={save} loading={saving} testID="admin-config-save" />
    </View>
  );
}
