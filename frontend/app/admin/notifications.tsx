import React, { useState } from "react";
import { Alert, Text, View } from "react-native";

import { adminApi } from "@/src/admin-api";
import { AdminSelect } from "@/src/components/admin/AdminSelect";
import { ConfirmDialog } from "@/src/components/admin/Dialog";
import { fonts } from "@/src/hooks/use-app-fonts";
import { space, useTheme } from "@/src/theme";
import { Btn, Field } from "@/src/components/ui";

const TARGET_OPTIONS = [
  { value: "all", label: "Todos os usuários" },
  { value: "category:client", label: "Somente clientes" },
  { value: "category:worker", label: "Somente fazedores" },
  { value: "user", label: "Um usuário específico (ID)" },
  { value: "city", label: "Uma cidade específica (ID)" },
];

const MASS_TARGETS = new Set(["all", "category:client", "category:worker"]);

export default function AdminNotifications() {
  const { colors } = useTheme();
  const [targetKind, setTargetKind] = useState<string | null>("all");
  const [targetValue, setTargetValue] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [result, setResult] = useState<{ recipient_count: number } | null>(null);

  const resolvedTarget = () => {
    if (!targetKind) return null;
    if (targetKind === "user") return targetValue.trim() ? `user:${targetValue.trim()}` : null;
    if (targetKind === "city") return targetValue.trim() ? `city:${targetValue.trim()}` : null;
    return targetKind;
  };

  const canSubmit = !!title.trim() && !!body.trim() && !!resolvedTarget();

  const submit = async () => {
    const target = resolvedTarget();
    if (!target) return;
    setBusy(true);
    try {
      const r = await adminApi.post("/admin/notifications", { title: title.trim(), body: body.trim(), target });
      setResult(r);
      setConfirmOpen(false);
      setTitle("");
      setBody("");
      Alert.alert("Enviado", `Notificação enviada para ${r.recipient_count} usuário${r.recipient_count === 1 ? "" : "s"}.`);
    } catch (e: any) {
      Alert.alert("Ops", e.message || "Não foi possível enviar a notificação.");
    } finally {
      setBusy(false);
    }
  };

  const onPressSend = () => {
    if (!canSubmit) return;
    if (targetKind && MASS_TARGETS.has(targetKind)) {
      setConfirmOpen(true);
    } else {
      submit();
    }
  };

  return (
    <View style={{ gap: space.lg, maxWidth: 520 }}>
      <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 13, lineHeight: 18 }}>
        Envie um aviso direto para os usuários do app. Envios em massa (todos, clientes ou fazedores) pedem confirmação extra.
      </Text>

      <AdminSelect label="Destinatário" value={targetKind} options={TARGET_OPTIONS} onChange={setTargetKind} testID="admin-notif-target" />

      {(targetKind === "user" || targetKind === "city") && (
        <Field
          label={targetKind === "user" ? "ID do usuário" : "ID da cidade"}
          value={targetValue}
          onChangeText={setTargetValue}
          autoCapitalize="none"
          testID="admin-notif-target-value"
        />
      )}

      <Field label="Título" value={title} onChangeText={setTitle} maxLength={120} testID="admin-notif-title" />
      <Field label="Mensagem" value={body} onChangeText={setBody} multiline maxLength={1000} style={{ minHeight: 100 }} testID="admin-notif-body" />

      <Btn title="Enviar notificação" disabled={!canSubmit || busy} loading={busy} onPress={onPressSend} testID="admin-notif-send" />

      {result && (
        <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 12 }}>
          Último envio: {result.recipient_count} destinatário{result.recipient_count === 1 ? "" : "s"}.
        </Text>
      )}

      <ConfirmDialog
        visible={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={submit}
        title="Confirmar envio em massa"
        message={`Isso vai notificar ${TARGET_OPTIONS.find((t) => t.value === targetKind)?.label.toLowerCase()}. Essa ação é registrada na auditoria.`}
        confirmLabel="Enviar mesmo assim"
        confirmWord="ENVIAR"
        danger
        loading={busy}
      />
    </View>
  );
}
