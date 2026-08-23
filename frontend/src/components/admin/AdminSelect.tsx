import { Ionicons } from "@expo/vector-icons";
import React, { useState } from "react";
import { Pressable, Text, View } from "react-native";

import { fonts } from "@/src/hooks/use-app-fonts";
import { space, useTheme } from "@/src/theme";
import { Dialog } from "@/src/components/admin/Dialog";

export type SelectOption = { value: string; label: string };

// Simple dropdown — opens a small centered picker (reusing Dialog) rather than an
// anchored popover, which needs layout measurement that's not worth it for the
// filter/form use cases this panel actually has.
export function AdminSelect({ label, value, options, onChange, placeholder = "Selecionar", testID }: {
  label?: string; value: string | null; options: SelectOption[]; onChange: (v: string | null) => void; placeholder?: string; testID?: string;
}) {
  const { colors } = useTheme();
  const [open, setOpen] = useState(false);
  const selected = options.find((o) => o.value === value);
  return (
    <View style={{ gap: 6 }}>
      {label ? <Text style={{ color: colors.muted, fontFamily: fonts.bodyBold, fontSize: 12, textTransform: "uppercase", letterSpacing: 0.6 }}>{label}</Text> : null}
      <Pressable
        testID={testID}
        onPress={() => setOpen(true)}
        style={{
          flexDirection: "row", alignItems: "center", justifyContent: "space-between",
          backgroundColor: colors.surface, borderWidth: 1.5, borderColor: colors.border, borderRadius: 14,
          paddingHorizontal: 14, minHeight: 50,
        }}
      >
        <Text style={{ color: selected ? colors.ink : colors.faint, fontFamily: fonts.body, fontSize: 15 }}>{selected?.label || placeholder}</Text>
        <Ionicons name="chevron-down" size={16} color={colors.faint} />
      </Pressable>

      <Dialog visible={open} onClose={() => setOpen(false)} title={label || placeholder} width={360}>
        <View style={{ gap: 4 }}>
          <Pressable
            onPress={() => { onChange(null); setOpen(false); }}
            style={{ paddingVertical: space.sm, paddingHorizontal: space.sm, borderRadius: 10, backgroundColor: value === null ? colors.primarySoft : "transparent" }}
          >
            <Text style={{ color: value === null ? colors.primary : colors.muted, fontFamily: fonts.bodySemiBold, fontSize: 14 }}>Todos</Text>
          </Pressable>
          {options.map((o) => (
            <Pressable
              key={o.value}
              testID={`${testID}-option-${o.value}`}
              onPress={() => { onChange(o.value); setOpen(false); }}
              style={{ paddingVertical: space.sm, paddingHorizontal: space.sm, borderRadius: 10, backgroundColor: value === o.value ? colors.primarySoft : "transparent" }}
            >
              <Text style={{ color: value === o.value ? colors.primary : colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 14 }}>{o.label}</Text>
            </Pressable>
          ))}
        </View>
      </Dialog>
    </View>
  );
}
