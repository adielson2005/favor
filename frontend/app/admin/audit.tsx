import React, { useEffect, useState } from "react";
import { Text, View } from "react-native";

import { adminApi } from "@/src/admin-api";
import { Column, Table } from "@/src/components/admin/Table";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useTheme } from "@/src/theme";

type AuditEntry = { id: string; admin_id: string; admin_name?: string; action: string; target: string; result?: string; created_at: string };

export default function AdminAudit() {
  const { colors } = useTheme();
  const [items, setItems] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminApi.get("/admin/audit").then(setItems).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const columns: Column<AuditEntry>[] = [
    { key: "admin_name", label: "Administrador", render: (a) => <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 13 }}>{a.admin_name || "—"}</Text> },
    { key: "action", label: "Ação", render: (a) => <Text style={{ color: colors.ink, fontFamily: fonts.body, fontSize: 13 }}>{a.action}</Text> },
    { key: "target", label: "Recurso", width: 2, render: (a) => <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 12 }} numberOfLines={1}>{a.target}</Text> },
    { key: "result", label: "Resultado", render: (a) => <Text style={{ color: a.result === "failure" ? colors.danger : colors.green, fontFamily: fonts.bodySemiBold, fontSize: 12 }}>{a.result === "failure" ? "falha" : "sucesso"}</Text> },
    { key: "created_at", label: "Quando", render: (a) => <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 12 }}>{new Date(a.created_at).toLocaleString("pt-BR")}</Text> },
  ];

  return <Table columns={columns} rows={items} loading={loading} emptyIcon="document-text-outline" emptyLabel="Nenhuma ação registrada ainda." />;
}
