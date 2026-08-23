import { Ionicons } from "@expo/vector-icons";
import React from "react";
import { Modal, Pressable, ScrollView, Text, View } from "react-native";

import { fonts } from "@/src/hooks/use-app-fonts";
import { space, useTheme } from "@/src/theme";

// Right-side slide-in panel for entity detail (user detail, order detail, ...).
export function Drawer({ visible, onClose, title, children, width = 440 }: {
  visible: boolean; onClose: () => void; title?: string; children: React.ReactNode; width?: number;
}) {
  const { colors } = useTheme();
  if (!visible) return null;
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={{ flex: 1, flexDirection: "row" }}>
        <Pressable style={{ flex: 1, backgroundColor: colors.scrim }} onPress={onClose} />
        <View style={{ width, maxWidth: "100%", backgroundColor: colors.surface, borderLeftWidth: 1, borderLeftColor: colors.border }}>
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: space.xl, paddingVertical: space.lg, borderBottomWidth: 1, borderBottomColor: colors.border }}>
            <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 17, flex: 1 }} numberOfLines={1}>{title}</Text>
            <Pressable onPress={onClose} hitSlop={8} testID="drawer-close"><Ionicons name="close" size={22} color={colors.muted} /></Pressable>
          </View>
          <ScrollView contentContainerStyle={{ padding: space.xl, gap: space.lg }}>{children}</ScrollView>
        </View>
      </View>
    </Modal>
  );
}
