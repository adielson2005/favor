import { Ionicons } from "@expo/vector-icons";
import { Tabs, useRouter } from "expo-router";
import React from "react";
import { Platform, Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useTheme } from "@/src/theme";

const TABS = [
  { name: "home", label: "Início", icon: "home-outline", iconActive: "home" },
  { name: "explore", label: "Explorar", icon: "compass-outline", iconActive: "compass" },
  { name: "create-placeholder", label: "", icon: "add", iconActive: "add" },
  { name: "messages", label: "Mensagens", icon: "chatbubble-outline", iconActive: "chatbubble" },
  { name: "profile", label: "Perfil", icon: "person-outline", iconActive: "person" },
] as const;

function TabBar({ state, navigation }: any) {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
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
                width: 50, height: 50, borderRadius: 17, backgroundColor: colors.primary, alignItems: "center",
                justifyContent: "center", marginTop: -4,
                shadowColor: colors.primary, shadowOpacity: 0.35, shadowRadius: 8, shadowOffset: { width: 0, height: 4 }, elevation: 6,
              }}>
                <Ionicons name="add" size={28} color={colors.onPrimary} />
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
            <Text style={{ fontSize: 10, fontWeight: active ? "700" : "600", color: active ? colors.primary : colors.faint }}>{tab.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export default function TabsLayout() {
  return (
    <Tabs screenOptions={{ headerShown: false }} tabBar={(props) => <TabBar {...props} />}>
      <Tabs.Screen name="home" />
      <Tabs.Screen name="explore" />
      <Tabs.Screen name="messages" />
      <Tabs.Screen name="profile" />
    </Tabs>
  );
}
