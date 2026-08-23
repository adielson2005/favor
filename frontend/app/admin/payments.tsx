import React, { useEffect, useState } from "react";
import { Text, View } from "react-native";

import { adminApi } from "@/src/admin-api";
import { Badge, BadgeTone } from "@/src/components/admin/Badge";
import { Column, Table } from "@/src/components/admin/Table";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useTheme } from "@/src/theme";

type Payment = {
  id: string; order_id: string; gross_amount: number; commission_amount: number;
  worker_net_amount: number; status: string; created_at: string;
};

const TONE: Record<string, BadgeTone> = { held: "green", released: "green", refunded: "neutral", pending: "amber" };

export default function AdminPayments() {
  const { colors } = useTheme();
  const [items, setItems] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminApi.get("/admin/payments").then(setItems).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const columns: Column<Payment>[] = [
    { key: "gross_amount", label: "Valor", render: (p) => <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 14 }}>R$ {p.gross_amount?.toFixed(2)}</Text> },
    { key: "commission_amount", label: "Comissão", render: (p) => <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 12 }}>R$ {p.commission_amount?.toFixed(2)}</Text> },
    { key: "worker_net_amount", label: "Líquido do fazedor", render: (p) => <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 12 }}>R$ {p.worker_net_amount?.toFixed(2)}</Text> },
    { key: "status", label: "Status", render: (p) => <Badge label={p.status} tone={TONE[p.status] || "neutral"} /> },
    { key: "order_id", label: "Pedido", render: (p) => <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 11 }}>{p.order_id.slice(0, 8)}</Text> },
    { key: "created_at", label: "Data", render: (p) => <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 12 }}>{new Date(p.created_at).toLocaleString("pt-BR")}</Text> },
  ];

  return (
    <View style={{ gap: 12 }}>
      <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 12 }}>
        Somente leitura — pagamentos nunca são editados diretamente, apenas por meio do fluxo real (webhook, conclusão, disputa).
      </Text>
      <Table columns={columns} rows={items} loading={loading} emptyIcon="card-outline" emptyLabel="Nenhum pagamento registrado." />
    </View>
  );
}
