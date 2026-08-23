import { Ionicons } from "@expo/vector-icons";
import React, { useState } from "react";
import { Modal, Pressable, ScrollView, Text, View } from "react-native";

import { fonts } from "@/src/hooks/use-app-fonts";
import { space, useTheme } from "@/src/theme";
import { Btn, Field } from "@/src/components/ui";

// Centered modal for admin forms/confirmations — distinct from the mobile-oriented
// bottom-sheet `Sheet` in ui.tsx. `confirmWord` turns this into the "type X to
// confirm" pattern the spec calls for on critical actions (backup restore, etc.).
export function Dialog({ visible, onClose, title, children, width = 480 }: {
  visible: boolean; onClose: () => void; title?: string; children: React.ReactNode; width?: number;
}) {
  const { colors } = useTheme();
  if (!visible) return null;
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={{ flex: 1, backgroundColor: colors.scrim, alignItems: "center", justifyContent: "center", padding: space.xl }} onPress={onClose}>
        <Pressable onPress={(e) => e.stopPropagation()} style={{ width: "100%", maxWidth: width, maxHeight: "86%", backgroundColor: colors.surface, borderRadius: 20, borderWidth: 1, borderColor: colors.border, overflow: "hidden" }}>
          {title ? (
            <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: space.xl, paddingTop: space.xl, paddingBottom: space.md }}>
              <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 17, flex: 1 }}>{title}</Text>
              <Pressable onPress={onClose} hitSlop={8} testID="dialog-close"><Ionicons name="close" size={22} color={colors.muted} /></Pressable>
            </View>
          ) : null}
          <ScrollView contentContainerStyle={{ paddingHorizontal: space.xl, paddingBottom: space.xl, gap: space.md }}>
            {children}
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

export function ConfirmDialog({ visible, onClose, onConfirm, title, message, confirmLabel = "Confirmar", danger, confirmWord, loading }: {
  visible: boolean; onClose: () => void; onConfirm: () => void; title: string; message?: string;
  confirmLabel?: string; danger?: boolean; confirmWord?: string; loading?: boolean;
}) {
  const { colors } = useTheme();
  const [typed, setTyped] = useState("");
  const locked = !!confirmWord && typed.trim().toUpperCase() !== confirmWord.toUpperCase();
  return (
    <Dialog visible={visible} onClose={onClose} title={title} width={420}>
      {message ? <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 14, lineHeight: 20 }}>{message}</Text> : null}
      {confirmWord ? (
        <Field
          label={`Digite ${confirmWord} para confirmar`}
          value={typed}
          onChangeText={setTyped}
          autoCapitalize="characters"
          testID="confirm-dialog-word-input"
        />
      ) : null}
      <View style={{ flexDirection: "row", gap: space.md, marginTop: space.sm }}>
        <View style={{ flex: 1 }}><Btn title="Cancelar" variant="ghost" onPress={onClose} /></View>
        <View style={{ flex: 1 }}>
          <Btn testID="confirm-dialog-confirm" title={confirmLabel} variant={danger ? "danger" : "primary"} onPress={onConfirm} disabled={locked || loading} loading={loading} />
        </View>
      </View>
    </Dialog>
  );
}
