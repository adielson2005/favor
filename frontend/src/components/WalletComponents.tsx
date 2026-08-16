import { Ionicons } from "@expo/vector-icons";
import React from "react";
import { Text, View } from "react-native";

import { WalletTransaction } from "@/src/api";
import { fonts } from "@/src/hooks/use-app-fonts";
import { radius, space, useTheme } from "@/src/theme";

export const WALLET_TYPE_LABELS: Record<string, string> = {
  DEPOSIT: "Depósito", PAYMENT: "Pagamento", COMMISSION: "Comissão", EARNING: "Ganho",
  REFUND: "Reembolso", WITHDRAWAL: "Saque", ADJUSTMENT: "Ajuste",
};

const FAILED_STATUSES = ["FAILED", "CANCELLED"];
const STATUS_TAGS: Record<string, string> = { PENDING: "Pendente", PROCESSING: "Processando", FAILED: "Não concluída", CANCELLED: "Cancelada" };

export function TransactionRow({ txn }: { txn: WalletTransaction }) {
  const { colors } = useTheme();
  const failed = FAILED_STATUSES.includes(txn.status);
  const isIn = txn.direction === "IN";
  // A failed/cancelled attempt never actually moved money — showing it with a +/-
  // sign and a bold color would read as a real transaction. It's kept in the ledger
  // for audit, but here it's visually flagged as "didn't happen" instead.
  const sign = failed ? "" : isIn ? "+" : txn.direction === "OUT" ? "−" : "";
  const color = failed ? colors.faint : isIn ? colors.green : txn.direction === "OUT" ? colors.ink : colors.muted;
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: space.md, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: space.md, opacity: failed ? 0.6 : 1 }}>
      <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: colors.alt, alignItems: "center", justifyContent: "center" }}>
        <Ionicons name={failed ? "close" : isIn ? "arrow-down" : "arrow-up"} size={16} color={color} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 14 }}>{WALLET_TYPE_LABELS[txn.type] || txn.type}</Text>
        <Text style={{ color: failed ? colors.danger : colors.faint, fontSize: 12 }} numberOfLines={1}>
          {failed ? `${STATUS_TAGS[txn.status]} — nenhum valor foi movido` : txn.description || STATUS_TAGS[txn.status] || txn.status}
        </Text>
      </View>
      <Text style={{ color, fontFamily: fonts.bodyBold, fontSize: 14, textDecorationLine: failed ? "line-through" : "none" }}>{sign} R$ {txn.amount.toFixed(2).replace(".", ",")}</Text>
    </View>
  );
}
