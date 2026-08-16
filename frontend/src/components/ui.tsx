import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import React from "react";
import { ActivityIndicator, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, TextInputProps, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { fonts } from "@/src/hooks/use-app-fonts";
import { Colors, useTheme } from "@/src/theme";

type Icon = keyof typeof Ionicons.glyphMap;

export function Btn({ title, onPress, variant = "primary", icon, small, disabled, loading, testID }: {
  title: string; onPress?: () => void; variant?: "primary" | "secondary" | "ghost" | "danger";
  icon?: Icon; small?: boolean; disabled?: boolean; loading?: boolean; testID?: string;
}) {
  const { colors } = useTheme();
  const bg = { primary: colors.primary, secondary: colors.alt, ghost: "transparent", danger: colors.dangerSoft }[variant];
  const fg = { primary: colors.onPrimary, secondary: colors.ink, ghost: colors.muted, danger: colors.danger }[variant];
  return (
    <Pressable
      testID={testID}
      disabled={disabled || loading}
      onPress={() => { if (Platform.OS !== "web") Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); onPress?.(); }}
      style={({ pressed }) => [{
        backgroundColor: bg, minHeight: small ? 40 : 52, borderRadius: small ? 12 : 16,
        paddingHorizontal: small ? 14 : 20, flexDirection: "row", alignItems: "center",
        justifyContent: "center", gap: 8, opacity: disabled ? 0.5 : pressed ? 0.85 : 1,
        transform: [{ scale: pressed ? 0.98 : 1 }],
      }]}
    >
      {loading ? <ActivityIndicator color={fg} size="small" /> : (
        <>
          <Text style={{ color: fg, fontFamily: fonts.bodyBold, fontSize: small ? 13 : 15 }}>{title}</Text>
          {icon ? <Ionicons name={icon} size={small ? 15 : 18} color={fg} /> : null}
        </>
      )}
    </Pressable>
  );
}

export function Chip({ label, active, onPress, icon, testID }: { label: string; active?: boolean; onPress?: () => void; icon?: Icon; testID?: string }) {
  const { colors } = useTheme();
  return (
    <Pressable
      testID={testID}
      onPress={onPress}
      style={({ pressed }) => [{
        flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 14, height: 38,
        borderRadius: 19, backgroundColor: active ? colors.ink : colors.surface,
        borderWidth: 1, borderColor: active ? colors.ink : colors.border, opacity: pressed ? 0.8 : 1,
      }]}
    >
      {icon ? <Ionicons name={icon} size={14} color={active ? colors.bg : colors.muted} /> : null}
      <Text style={{ color: active ? colors.bg : colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 13 }}>{label}</Text>
    </Pressable>
  );
}

export function Stars({ value, size = 16, onChange }: { value: number; size?: number; onChange?: (v: number) => void }) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", gap: onChange ? 8 : 2 }}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Pressable key={i} disabled={!onChange} onPress={() => onChange?.(i)} testID={`star-${i}`} hitSlop={6}>
          <Ionicons name={i <= Math.round(value) ? "star" : "star-outline"} size={size} color={colors.amber} />
        </Pressable>
      ))}
    </View>
  );
}

export function Avatar({ name, initials, size = 44 }: { name?: string; initials?: string; size?: number }) {
  const { colors } = useTheme();
  const label = initials || (name || "?").split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  return (
    <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" }}>
      <Text style={{ color: colors.primary, fontFamily: fonts.bodyBold, fontSize: size * 0.36 }}>{label}</Text>
    </View>
  );
}

export function Row({ icon, label, value, onPress, danger, testID }: { icon: Icon; label: string; value?: string; onPress?: () => void; danger?: boolean; testID?: string }) {
  const { colors } = useTheme();
  return (
    <Pressable testID={testID} onPress={onPress} style={({ pressed }) => [{ flexDirection: "row", alignItems: "center", gap: 14, minHeight: 54, opacity: pressed ? 0.6 : 1 }]}>
      <Ionicons name={icon} size={20} color={danger ? colors.danger : colors.muted} />
      <Text style={{ flex: 1, color: danger ? colors.danger : colors.ink, fontFamily: fonts.body, fontSize: 15 }}>{label}</Text>
      {value ? <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 13 }}>{value}</Text> : null}
      {onPress ? <Ionicons name="chevron-forward" size={16} color={colors.faint} /> : null}
    </Pressable>
  );
}

export function EmptyState({ icon, title, body, actionTitle, onAction }: { icon: Icon; title: string; body?: string; actionTitle?: string; onAction?: () => void }) {
  const { colors } = useTheme();
  return (
    <View style={{ alignItems: "center", paddingVertical: 48, paddingHorizontal: 32, gap: 8 }}>
      <View style={{ width: 64, height: 64, borderRadius: 32, backgroundColor: colors.alt, alignItems: "center", justifyContent: "center", marginBottom: 6 }}>
        <Ionicons name={icon} size={26} color={colors.muted} />
      </View>
      <Text style={{ color: colors.ink, fontFamily: fonts.bodyBold, fontSize: 16, textAlign: "center" }}>{title}</Text>
      {body ? <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 14, textAlign: "center", lineHeight: 20 }}>{body}</Text> : null}
      {actionTitle ? <View style={{ marginTop: 14 }}><Btn title={actionTitle} onPress={onAction} small variant="secondary" /></View> : null}
    </View>
  );
}

export function Field({ label, error, ...props }: TextInputProps & { label?: string; error?: string }) {
  const { colors } = useTheme();
  const [focused, setFocused] = React.useState(false);
  return (
    <View style={{ gap: 6 }}>
      {label ? <Text style={{ color: colors.muted, fontFamily: fonts.bodyBold, fontSize: 12, textTransform: "uppercase", letterSpacing: 0.6 }}>{label}</Text> : null}
      <TextInput
        placeholderTextColor={colors.faint}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        {...props}
        style={[{
          backgroundColor: colors.surface, borderWidth: 1.5, borderRadius: 14,
          borderColor: error ? colors.danger : focused ? colors.primary : colors.border,
          color: colors.ink, fontFamily: fonts.body, fontSize: 15, paddingHorizontal: 14, paddingVertical: 13, minHeight: 50,
        }, props.style]}
      />
      {error ? <Text style={{ color: colors.danger, fontFamily: fonts.body, fontSize: 12 }}>{error}</Text> : null}
    </View>
  );
}

export function Segmented<T extends string>({ options, value, onChange }: { options: { key: T; label: string }[]; value: T; onChange: (v: T) => void }) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", backgroundColor: colors.alt, borderRadius: 14, padding: 3 }}>
      {options.map((option) => (
        <Pressable
          key={option.key}
          testID={`segment-${option.key}`}
          onPress={() => onChange(option.key)}
          style={{ flex: 1, height: 40, borderRadius: 11, alignItems: "center", justifyContent: "center", backgroundColor: value === option.key ? colors.surface : "transparent", ...(value === option.key && Platform.OS === "android" ? { elevation: 1 } : {}) }}
        >
          <Text style={{ color: value === option.key ? colors.ink : colors.muted, fontFamily: fonts.bodyBold, fontSize: 13 }}>{option.label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

export function Sheet({ visible, onClose, title, children, scroll = true }: { visible: boolean; onClose: () => void; title?: string; children: React.ReactNode; scroll?: boolean }) {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const Body = scroll ? ScrollView : View;
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={{ flex: 1, backgroundColor: colors.scrim }} onPress={onClose} />
      <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: "86%", paddingBottom: Math.max(insets.bottom, 16) }}>
        <View style={{ width: 40, height: 4, borderRadius: 2, backgroundColor: colors.border, alignSelf: "center", marginTop: 10 }} />
        {title ? (
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 20, paddingTop: 14, paddingBottom: 4 }}>
            <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 18 }}>{title}</Text>
            <Pressable onPress={onClose} hitSlop={8} testID="sheet-close"><Ionicons name="close" size={22} color={colors.muted} /></Pressable>
          </View>
        ) : null}
        <Body style={{ paddingHorizontal: 20 }} keyboardShouldPersistTaps="handled">{children}</Body>
      </View>
    </Modal>
  );
}

export function SectionTitle({ title, action, onAction }: { title: string; action?: string; onAction?: () => void }) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
      <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 17 }}>{title}</Text>
      {action ? <Pressable onPress={onAction} hitSlop={8}><Text style={{ color: colors.primary, fontFamily: fonts.bodyBold, fontSize: 13 }}>{action}</Text></Pressable> : null}
    </View>
  );
}

export function Skeleton({ height = 84, radius = 16 }: { height?: number; radius?: number }) {
  const { colors } = useTheme();
  return <View style={{ height, borderRadius: radius, backgroundColor: colors.alt, opacity: 0.7 }} />;
}

export const shared = (colors: Colors) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  pad: { paddingHorizontal: 20 },
  h1: { color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 24, letterSpacing: -0.5 },
  body: { color: colors.muted, fontFamily: fonts.body, fontSize: 14, lineHeight: 21 },
  divider: { height: 1, backgroundColor: colors.border, marginVertical: 4 },
});
