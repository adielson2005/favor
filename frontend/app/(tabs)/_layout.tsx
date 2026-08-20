import { Ionicons } from "@expo/vector-icons";
import { Tabs, usePathname, useRouter } from "expo-router";
import React from "react";
import { Platform, Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Brand, LogoMark } from "@/src/components/Logo";
import { Avatar, Btn } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useBreakpoint } from "@/src/hooks/use-breakpoint";
import { useRequireAuth } from "@/src/hooks/use-require-auth";
import { useApp } from "@/src/state";
import { radius, space, useTheme } from "@/src/theme";

const NAV_MAX_WIDTH = 1280;

// Exactly 5 tabs — Início/Pedidos/Mensagens/Carteira/Perfil. "Pedir ajuda" isn't a
// tab anymore: Home has its own CTA button, and the desktop Navbar renders one too
// (both independent of this list), so creating an order loses only its bottom-bar
// shortcut, not the flow itself.
const TABS = [
  { name: "home", label: "Início", icon: "home-outline", iconActive: "home" },
  { name: "pedidos", label: "Pedidos", icon: "list-outline", iconActive: "list" },
  { name: "messages", label: "Mensagens", icon: "chatbubble-outline", iconActive: "chatbubble" },
  { name: "wallet", label: "Carteira", icon: "wallet-outline", iconActive: "wallet" },
  { name: "profile", label: "Perfil", icon: "person-outline", iconActive: "person" },
] as const;

// Mobile/tablet: standard bottom bar. Hidden entirely on desktop — Navbar (below)
// takes over navigation there, rendered as a real flex sibling instead of fighting
// the tab navigator's own bottom-bar layout slot.
function TabBar({ state, navigation }: any) {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { isDesktop } = useBreakpoint();
  if (isDesktop) return null;
  const activeRoute = state.routes[state.index]?.name;

  return (
    <View style={{
      flexDirection: "row", backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border,
      paddingBottom: Math.max(insets.bottom, Platform.OS === "ios" ? 20 : 10), paddingTop: 8, paddingHorizontal: 8,
    }}>
      {TABS.map((tab) => {
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

// Desktop: a full-width top navbar (marketplace-site pattern — logo, nav links, CTA,
// account — instead of an app-like left sidebar). A normal flex sibling stacked above
// the screen content, so pages below get the full window width to work with.
function Navbar() {
  const { colors } = useTheme();
  const router = useRouter();
  const pathname = usePathname();
  const insets = useSafeAreaInsets();
  const { me, unread } = useApp();

  return (
    <View style={{ backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.border, paddingTop: insets.top }}>
      <View style={{
        flexDirection: "row", alignItems: "center", height: 68, gap: space.xxl,
        width: "100%", maxWidth: NAV_MAX_WIDTH, alignSelf: "center", paddingHorizontal: space.xxl,
      }}>
        <Pressable testID="navbar-home" onPress={() => router.push("/(tabs)/home")}>
          <Brand size={30} />
        </Pressable>

        <View style={{ flexDirection: "row", alignItems: "center", gap: space.xl }}>
          {TABS.map((tab) => {
            const active = pathname.startsWith(`/${tab.name}`);
            return (
              <Pressable key={tab.name} testID={`navbar-${tab.name}`} onPress={() => router.push(`/${tab.name}` as never)} style={{ paddingVertical: space.sm }}>
                <Text style={{ fontFamily: active ? fonts.bodyBold : fonts.bodySemiBold, fontSize: 15, color: active ? colors.primary : colors.muted }}>{tab.label}</Text>
                {active && <View style={{ height: 2, borderRadius: 1, backgroundColor: colors.primary, marginTop: 6 }} />}
              </Pressable>
            );
          })}
        </View>

        <View style={{ flex: 1 }} />

        <View style={{ flexDirection: "row", alignItems: "center", gap: space.lg }}>
          <Btn testID="navbar-ask-help" title="Pedir ajuda" onPress={() => router.push("/create")} small />
          <Pressable testID="navbar-notifications" onPress={() => router.push("/notifications")} hitSlop={6} style={{ width: 40, height: 40, borderRadius: radius.pill, backgroundColor: colors.alt, alignItems: "center", justifyContent: "center" }}>
            <Ionicons name="notifications-outline" size={18} color={colors.ink} />
            {unread > 0 && <View style={{ position: "absolute", top: 7, right: 8, width: 8, height: 8, borderRadius: 4, backgroundColor: colors.danger, borderWidth: 1.5, borderColor: colors.alt }} />}
          </Pressable>
          <Pressable testID="navbar-profile" onPress={() => router.push("/(tabs)/profile")}>
            {me ? <Avatar name={me.name} initials={me.initials} size={38} photo={me.avatar_b64} /> : <LogoMark size={38} />}
          </Pressable>
        </View>
      </View>
    </View>
  );
}

export default function TabsLayout() {
  const { colors } = useTheme();
  const { isDesktop } = useBreakpoint();
  useRequireAuth();
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      {isDesktop && <Navbar />}
      <View style={{ flex: 1 }}>
        <Tabs screenOptions={{ headerShown: false }} tabBar={(props) => <TabBar {...props} />}>
          <Tabs.Screen name="home" />
          <Tabs.Screen name="pedidos" />
          <Tabs.Screen name="messages" />
          <Tabs.Screen name="wallet" />
          <Tabs.Screen name="profile" />
        </Tabs>
      </View>
    </View>
  );
}
