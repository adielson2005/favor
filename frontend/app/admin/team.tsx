import React, { useCallback, useEffect, useState } from "react";
import { Alert, Text, View } from "react-native";

import { adminApi } from "@/src/admin-api";
import { Badge } from "@/src/components/admin/Badge";
import { Dialog } from "@/src/components/admin/Dialog";
import { Column, Table } from "@/src/components/admin/Table";
import { fonts } from "@/src/hooks/use-app-fonts";
import { space, useTheme } from "@/src/theme";
import { Btn, Field } from "@/src/components/ui";

type Role = "OWNER" | "MANAGER" | "SUPPORT" | "MAINTENANCE";
type Member = { id: string; name: string; email: string; role: Role; active: boolean; last_login_at: string | null; totp_enabled: boolean };

const ROLE_LABELS: Record<Role, string> = {
  OWNER: "Admin principal", MANAGER: "Gerente", SUPPORT: "Suporte", MAINTENANCE: "Manutenção",
};
const ROLE_TONE: Record<Role, "primary" | "neutral"> = {
  OWNER: "primary", MANAGER: "neutral", SUPPORT: "neutral", MAINTENANCE: "neutral",
};

export default function AdminTeam() {
  const { colors } = useTheme();
  const [items, setItems] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("SUPPORT");
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    adminApi.get("/admin/team").then(setItems).catch(() => {}).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    setSaving(true);
    try {
      await adminApi.post("/admin/team", { name, email, password, role });
      setCreateOpen(false);
      setName(""); setEmail(""); setPassword(""); setRole("SUPPORT");
      load();
    } catch (e: any) {
      Alert.alert("Não foi possível criar", e.message || "Tente novamente.");
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (m: Member) => {
    try {
      await adminApi.patch(`/admin/team/${m.id}`, { active: !m.active });
      load();
    } catch (e: any) {
      Alert.alert("Ops", e.message || "Não foi possível concluir.");
    }
  };

  const revokeSessions = async (m: Member) => {
    try {
      await adminApi.post(`/admin/team/${m.id}/revoke-sessions`);
      Alert.alert("Sessões encerradas", `${m.name} vai precisar entrar novamente.`);
    } catch (e: any) {
      Alert.alert("Ops", e.message || "Não foi possível concluir.");
    }
  };

  const columns: Column<Member>[] = [
    { key: "name", label: "Nome", width: 2, render: (m) => (
      <View>
        <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 13 }}>{m.name}</Text>
        <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 11 }}>{m.email}</Text>
      </View>
    ) },
    { key: "role", label: "Papel", render: (m) => <Badge label={ROLE_LABELS[m.role]} tone={ROLE_TONE[m.role]} /> },
    { key: "active", label: "Status", render: (m) => <Badge label={m.active ? "Ativo" : "Desativado"} tone={m.active ? "green" : "danger"} /> },
    { key: "totp_enabled", label: "2FA", render: (m) => <Text style={{ color: m.totp_enabled ? colors.green : colors.faint, fontFamily: fonts.body, fontSize: 12 }}>{m.totp_enabled ? "Ativado" : "—"}</Text> },
    { key: "last_login_at", label: "Último acesso", render: (m) => <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 12 }}>{m.last_login_at ? new Date(m.last_login_at).toLocaleString("pt-BR") : "nunca"}</Text> },
    { key: "actions", label: "", render: (m) => (
      <View style={{ flexDirection: "row", gap: space.sm }}>
        <Btn small variant="secondary" title={m.active ? "Desativar" : "Ativar"} onPress={() => toggleActive(m)} testID={`admin-team-${m.id}-toggle`} />
        <Btn small variant="ghost" title="Encerrar sessões" onPress={() => revokeSessions(m)} />
      </View>
    ) },
  ];

  return (
    <View style={{ gap: space.lg }}>
      <View style={{ flexDirection: "row", justifyContent: "flex-end" }}>
        <Btn title="Novo membro" onPress={() => setCreateOpen(true)} testID="admin-team-new" />
      </View>

      <Table columns={columns} rows={items} loading={loading} emptyIcon="shield-checkmark-outline" emptyLabel="Nenhum membro cadastrado." />

      <Dialog visible={createOpen} onClose={() => setCreateOpen(false)} title="Novo membro da equipe">
        <Field label="Nome" value={name} onChangeText={setName} testID="admin-team-name-input" />
        <Field label="E-mail" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" testID="admin-team-email-input" />
        <Field label="Senha" value={password} onChangeText={setPassword} secureTextEntry testID="admin-team-password-input" />
        <View style={{ flexDirection: "row", gap: space.sm, flexWrap: "wrap" }}>
          {(Object.keys(ROLE_LABELS) as Role[]).map((r) => (
            <View key={r} style={{ minWidth: 110, flexGrow: 1 }}>
              <Btn small variant={role === r ? "primary" : "secondary"} title={ROLE_LABELS[r]} onPress={() => setRole(r)} testID={`admin-team-role-${r}`} />
            </View>
          ))}
        </View>
        <Btn title="Criar" onPress={create} loading={saving} disabled={!name.trim() || !email.trim() || password.length < 8} testID="admin-team-create-submit" />
      </Dialog>
    </View>
  );
}
