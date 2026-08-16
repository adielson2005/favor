import { Ionicons } from "@expo/vector-icons";
import { Tabs, usePathname, useRouter } from "expo-router";
import React from "react";
import { Platform, Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Brand } from "@/src/components/Logo";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useBreakpoint } from "@/src/hooks/use-breakpoint";
import { space, useTheme } from "@/src/theme";

const SIDEBAR_WIDTH = 232;

const TABS = [
  { name: "home", label: "Início", icon: "home-outline", iconActive: "home" },
  { name: "explore", label: "Explorar", icon: "compass-outline", iconActive: "compass" },
  { name: "create-placeholder", label: "Pedir ajuda", icon: "add", iconActive: "add" },
  { name: "messages", label: "Mensagens", icon: "chatbubble-outline", iconActive: "chatbubble" },
  { name: "profile", label: "Perfil", icon: "person-outline", iconActive: "person" },
] as const;

// Mobile/tablet: standard bottom bar. Hidden entirely on desktop — Sidebar (below)
// takes over navigation there, rendered as a real flex sibling instead of fighting
// the tab navigator's own bottom-bar layout slot.
function TabBar({ state, navigation }: any) {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { isDesktop } = useBreakpoint();
  if (isDesktop) return null;
  const activeRoute = state.routes[state.index]?.name;

  return (
    <View style={{
      flexDirection: "row", backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border,
      paddingBottom: Math.max(insets.bottom, Platform.OS === "ios" ? 20 : 10), paddingTop: 8, paddingHorizontal: 8,
    }}>
      {TABS.map((tab) => {
        if (tab.name === "create-placeholder") {
          return (
            <Pressable
              key="create"
              testID="tab-create-button"
              onPress={() => router.push("/create")}
              style={({ pressed }) => [{ flex: 1, alignItems: "center", justifyContent: "flex-start", transform: [{ scale: pressed ? 0.94 : 1 }] }]}
            >
              <View style={{
                width: 50, height: 50, borderRadius: 17, backgroundColor: colors.accent, alignItems: "center",
                justifyContent: "center", marginTop: -4, transform: [{ rotate: "-8deg" }],
                shadowColor: colors.accent, shadowOpacity: 0.4, shadowRadius: 8, shadowOffset: { width: 0, height: 4 }, elevation: 6,
              }}>
                <Ionicons name="add" size={28} color={colors.onAccent} />
              </View>
            </Pressable>
          );
        }
        const active = activeRoute === tab.name;
        return (
          <Pressable
            key={tab.name}
            testID={`tab-${tab.name}`}
            onPress={() => navigation.navigate(tab.name)}
            style={{ flex: 1, alignItems: "center", gap: 3, minHeight: 48, justifyContent: "center" }}
          >
            <Ionicons name={(active ? tab.iconActive : tab.icon) as keyof typeof Ionicons.glyphMap} size={22} color={active ? colors.primary : colors.faint} />
            <Text style={{ fontSize: 10, fontFamily: active ? fonts.bodyBold : fonts.bodySemiBold, color: active ? colors.primary : colors.faint }}>{tab.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

// Desktop: a fixed left sidebar (Instagram/Slack pattern), a normal flex sibling of
// the screen content — not routed through the tab navigator's bar slot, so it can't
// end up fighting react-navigation's own height reservation for that slot.
function Sidebar() {
  const { colors } = useTheme();
  const router = useRouter();
  const pathname = usePathname();

  return (
    <View style={{
      width: SIDEBAR_WIDTH, backgroundColor: colors.surface, borderRightWidth: 1, borderRightColor: colors.border,
      paddingTop: space.xxl, paddingHorizontal: space.lg, gap: space.xs,
    }}>
      <View style={{ paddingHorizontal: space.sm, marginBottom: space.xxxl }}>
        <Brand size={34} />
      </View>
      {TABS.map((tab) => {
        const active = tab.name !== "create-placeholder" && pathname.startsWith(`/${tab.name}`);
        return (
          <Pressable
            key={tab.name}
            testID={`sidebar-${tab.name}`}
            onPress={() => router.push(tab.name === "create-placeholder" ? "/create" : (`/${tab.name}` as never))}
            style={({ pressed }) => [{
              flexDirection: "row", alignItems: "center", gap: space.md, height: 46, borderRadius: 12,
              paddingHorizontal: space.md, backgroundColor: active ? colors.primarySoft : pressed ? colors.alt : "transparent",
            }]}
          >
            <Ionicons name={(active ? tab.iconActive : tab.icon) as keyof typeof Ionicons.glyphMap} size={21} color={active ? colors.primary : colors.muted} />
            <Text style={{ fontFamily: active ? fonts.bodyBold : fonts.bodySemiBold, fontSize: 14, color: active ? colors.primary : colors.ink }}>{tab.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export default function TabsLayout() {
  const { colors } = useTheme();
  const { isDesktop } = useBreakpoint();
  return (
    <View style={{ flex: 1, flexDirection: "row", backgroundColor: colors.bg }}>
      {isDesktop && <Sidebar />}
      <View style={{ flex: 1 }}>
        <Tabs screenOptions={{ headerShown: false }} tabBar={(props) => <TabBar {...props} />}>
          <Tabs.Screen name="home" />
          <Tabs.Screen name="explore" />
          <Tabs.Screen name="messages" />
          <Tabs.Screen name="profile" />
        </Tabs>
      </View>
    </View>
  );
}
