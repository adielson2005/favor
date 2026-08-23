import { Ionicons } from "@expo/vector-icons";
import React from "react";
import { Pressable, ScrollView, Text, View } from "react-native";

import { fonts } from "@/src/hooks/use-app-fonts";
import { radius, space, useTheme } from "@/src/theme";
import { EmptyState, Skeleton } from "@/src/components/ui";

export type Column<T> = {
  key: string;
  label: string;
  width?: number; // flex-grow weight; omit for auto/content-sized-ish columns
  sortable?: boolean;
  render?: (row: T) => React.ReactNode;
};

export type SortState = { key: string; dir: "asc" | "desc" };

export function Table<T extends { id: string }>({
  columns, rows, loading, emptyIcon = "file-tray-outline", emptyLabel = "Nada para mostrar.",
  onRowPress, sort, onSortChange, page = 0, pageSize = 50, total, onPageChange,
}: {
  columns: Column<T>[];
  rows: T[];
  loading?: boolean;
  emptyIcon?: React.ComponentProps<typeof Ionicons>["name"];
  emptyLabel?: string;
  onRowPress?: (row: T) => void;
  sort?: SortState;
  onSortChange?: (key: string) => void;
  page?: number;
  pageSize?: number;
  total?: number;
  onPageChange?: (page: number) => void;
}) {
  const { colors } = useTheme();

  if (loading) {
    return <View style={{ gap: space.sm }}>{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} height={44} radius={10} />)}</View>;
  }

  if (rows.length === 0) {
    return <EmptyState icon={emptyIcon} title={emptyLabel} />;
  }

  const showPagination = typeof total === "number" && typeof onPageChange === "function";
  const from = page * pageSize + 1;
  const to = Math.min(page * pageSize + rows.length, total ?? 0);

  return (
    <View style={{ borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg, overflow: "hidden", backgroundColor: colors.surface }}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View style={{ minWidth: "100%" }}>
          <View style={{ flexDirection: "row", borderBottomWidth: 1, borderBottomColor: colors.border }}>
            {columns.map((c) => (
              <Pressable
                key={c.key}
                disabled={!c.sortable}
                onPress={() => c.sortable && onSortChange?.(c.key)}
                style={{ flex: c.width ?? 1, minWidth: 120, flexDirection: "row", alignItems: "center", gap: 4, paddingHorizontal: space.md, paddingVertical: 11 }}
              >
                <Text style={{ color: colors.faint, fontFamily: fonts.bodySemiBold, fontSize: 12 }}>{c.label}</Text>
                {c.sortable && sort?.key === c.key ? (
                  <Ionicons name={sort.dir === "asc" ? "arrow-up" : "arrow-down"} size={12} color={colors.muted} />
                ) : null}
              </Pressable>
            ))}
          </View>
          {rows.map((row, i) => (
            <Pressable
              key={row.id}
              testID={`table-row-${row.id}`}
              onPress={onRowPress ? () => onRowPress(row) : undefined}
              style={({ pressed }) => [{
                flexDirection: "row", alignItems: "center",
                borderTopWidth: i === 0 ? 0 : 1, borderTopColor: colors.border,
                backgroundColor: pressed && onRowPress ? colors.bg : "transparent",
              }]}
            >
              {columns.map((c) => (
                <View key={c.key} style={{ flex: c.width ?? 1, minWidth: 120, paddingHorizontal: space.md, paddingVertical: space.md + 2 }}>
                  {c.render ? c.render(row) : <Text style={{ color: colors.ink, fontFamily: fonts.body, fontSize: 13 }} numberOfLines={1}>{String((row as any)[c.key] ?? "—")}</Text>}
                </View>
              ))}
            </Pressable>
          ))}
        </View>
      </ScrollView>

      {showPagination && (
        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: space.md, paddingVertical: space.sm, borderTopWidth: 1, borderTopColor: colors.border }}>
          <Text style={{ color: colors.faint, fontFamily: fonts.body, fontSize: 12 }}>
            {total! > 0 ? `${from}–${to} de ${total}` : "0 resultados"}
          </Text>
          <View style={{ flexDirection: "row", gap: space.sm }}>
            <Pressable testID="table-prev-page" disabled={page === 0} onPress={() => onPageChange!(page - 1)} hitSlop={8} style={{ opacity: page === 0 ? 0.35 : 1 }}>
              <Ionicons name="chevron-back" size={18} color={colors.ink} />
            </Pressable>
            <Pressable testID="table-next-page" disabled={to >= (total ?? 0)} onPress={() => onPageChange!(page + 1)} hitSlop={8} style={{ opacity: to >= (total ?? 0) ? 0.35 : 1 }}>
              <Ionicons name="chevron-forward" size={18} color={colors.ink} />
            </Pressable>
          </View>
        </View>
      )}
    </View>
  );
}
