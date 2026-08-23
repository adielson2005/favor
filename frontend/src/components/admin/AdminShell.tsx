import { Ionicons } from "@expo/vector-icons";
import { useRouter, useSegments } from "expo-router";
import React, { useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { hasPermission } from "@/src/admin-api";
import { useAdminAuth } from "@/src/admin-auth";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useBreakpoint } from "@/src/hooks/use-breakpoint";
import { radius, space, useTheme } from "@/src/theme";
import { Avatar } from "@/src/components/ui";

type NavItem = { key: string; label: string; icon: React.ComponentProps<typeof Ionicons>["name"]; href: string; permission: string | string[] };
type NavSection = { label: string; items: NavItem[] };

const SECTIONS: NavSection[] = [
  {
    label: "Geral",
    items: [
      { key: "dashboard", label: "Dashboard", icon: "grid-outline", href: "/admin", permission: "dashboard.view" },
      { key: "supervision", label: "Supervisão", icon: "eye-outline", href: "/admin/supervision", permission: "supervision.view" },
    ],
  },
  {
    label: "Operação",
    items: [
      { key: "users", label: "Usuários", icon: "people-outline", href: "/admin/users", permission: "users.view" },
      { key: "orders", label: "Pedidos", icon: "briefcase-outline", href: "/admin/orders", permission: "orders.view" },
      { key: "payments", label: "Pagamentos", icon: "card-outline", href: "/admin/payments", permission: "payments.view" },
      { key: "withdrawals", label: "Saques", icon: "cash-outline", href: "/admin/withdrawals", permission: "withdrawals.view" },
      { key: "disputes", label: "Disputas", icon: "warning-outline", href: "/admin/disputes", permission: "disputes.view" },
      { key: "reports", label: "Denúncias", icon: "flag-outline", href: "/admin/reports", permission: "reports.view" },
      { key: "support", label: "Suporte", icon: "chatbox-ellipses-outline", href: "/admin/support", permission: ["support.view", "maintenance.view"] },
    ],
  },
  {
    label: "Segurança",
    items: [
      { key: "security", label: "Segurança", icon: "shield-outline", href: "/admin/security", permission: ["risk.view", "security_events.view"] },
      { key: "audit", label: "Auditoria", icon: "document-text-outline", href: "/admin/audit", permission: "audit.view" },
    ],
  },
  {
    label: "Configuração",
    items: [
      { key: "categories", label: "Categorias", icon: "pricetags-outline", href: "/admin/categories", permission: "categories.manage" },
      { key: "locations", label: "Localidades", icon: "location-outline", href: "/admin/locations", permission: "geo.manage" },
      { key: "feature-flags", label: "Feature flags", icon: "flag-outline", href: "/admin/feature-flags", permission: "feature_flags.view" },
      { key: "notifications", label: "Notificações", icon: "megaphone-outline", href: "/admin/notifications", permission: "notifications.send" },
      { key: "config", label: "Configurações", icon: "settings-outline", href: "/admin/config", permission: "config.view" },
      { key: "team", label: "Equipe", icon: "shield-checkmark-outline", href: "/admin/team", permission: "admin_team.view" },
    ],
  },
];

const ROLE_LABELS: Record<string, string> = { OWNER: "Admin principal", MANAGER: "Gerente", SUPPORT: "Suporte", MAINTENANCE: "Manutenção" };

function canSee(admin: ReturnType<typeof useAdminAuth>["admin"], permission: string | string[]): boolean {
  return Array.isArray(permission) ? permission.some((p) => hasPermission(admin, p)) : hasPermission(admin, permission);
}

export function AdminShell({ title, subtitle, icon, children }: {
  title: string; subtitle?: string; icon?: React.ComponentProps<typeof Ionicons>["name"]; children: React.ReactNode;
}) {
  const { colors } = useTheme();
  const router = useRouter();
  const segments = useSegments();
  const insets = useSafeAreaInsets();
  const { admin, logout } = useAdminAuth();
  const { isDesktop } = useBreakpoint();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const activeKey = segments[1] || "dashboard";
  const visibleSections = SECTIONS.map((s) => ({ ...s, items: s.items.filter((n) => canSee(admin, n.permission)) })).filter((s) => s.items.length > 0);

  const sidebar = (
    <View style={{ width: 260, backgroundColor: colors.bg, borderRightWidth: 1, borderRightColor: colors.border, paddingTop: insets.top }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: space.xl, height: 64 }}>
        <View style={{ width: 34, height: 34, borderRadius: 12, backgroundColor: colors.ink, alignItems: "center", justifyContent: "center" }}>
          <Text style={{ color: colors.bg, fontFamily: fonts.headingExtraBold, fontSize: 15 }}>f</Text>
        </View>
        <View>
          <Text style={{ color: colors.ink, fontFamily: fonts.headingBold, fontSize: 16, letterSpacing: -0.2 }}>fazum</Text>
          <Text style={{ color: colors.faint, fontFamily: fonts.bodyMedium, fontSize: 11 }}>painel administrativo</Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={{ paddingHorizontal: space.lg, paddingBottom: space.lg, gap: space.lg }}>
        {visibleSections.map((section) => (
          <View key={section.label}>
            <Text style={{
              color: colors.faint, fontFamily: fonts.bodyBold, fontSize: 11, textTransform: "uppercase",
              letterSpacing: 1, marginBottom: 6, marginLeft: 4,
            }}>
              {section.label}
            </Text>
            <View style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg, overflow: "hidden" }}>
              {section.items.map((item, i) => {
                const active = item.key === activeKey;
                return (
                  <React.Fragment key={item.key}>
                    {i > 0 && <View style={{ height: 1, backgroundColor: colors.border, marginLeft: 56 }} />}
                    <Pressable
                      testID={`admin-nav-${item.key}`}
                      onPress={() => { router.push(item.href as any); setDrawerOpen(false); }}
                      style={({ pressed }) => [{
                        flexDirection: "row", alignItems: "center", gap: 12, minHeight: 46, paddingHorizontal: space.md,
                        backgroundColor: active ? colors.primarySoft : pressed ? colors.alt : "transparent",
                      }]}
                    >
                      <View style={{
                        width: 28, height: 28, borderRadius: 14, alignItems: "center", justifyContent: "center",
                        backgroundColor: active ? colors.primary : colors.alt,
                      }}>
                        <Ionicons name={item.icon} size={14} color={active ? colors.onPrimary : colors.muted} />
                      </View>
                      <Text style={{ color: active ? colors.primary : colors.ink, fontFamily: active ? fonts.bodySemiBold : fonts.bodyMedium, fontSize: 13.5 }}>
                        {item.label}
                      </Text>
                    </Pressable>
                  </React.Fragment>
                );
              })}
            </View>
          </View>
        ))}
      </ScrollView>

      <View style={{
        flexDirection: "row", alignItems: "center", gap: 10, marginHorizontal: space.lg, marginBottom: space.lg,
        padding: space.sm, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg,
      }}>
        <Avatar name={admin?.name} size={34} />
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 12.5 }} numberOfLines={1}>{admin?.name}</Text>
          <Text style={{ color: colors.faint, fontFamily: fonts.bodyMedium, fontSize: 11 }} numberOfLines={1}>{ROLE_LABELS[admin?.role || ""] || admin?.role}</Text>
        </View>
        <Pressable testID="admin-logout" onPress={logout} hitSlop={8} style={{ width: 30, height: 30, borderRadius: 15, alignItems: "center", justifyContent: "center", backgroundColor: colors.dangerSoft }}>
          <Ionicons name="log-out-outline" size={15} color={colors.danger} />
        </Pressable>
      </View>
    </View>
  );

  return (
    <View style={{ flex: 1, flexDirection: "row", backgroundColor: colors.bg }}>
      {isDesktop && sidebar}
      {!isDesktop && drawerOpen && (
        <View style={{ position: "absolute", top: 0, bottom: 0, left: 0, zIndex: 20, flexDirection: "row" }}>
          {sidebar}
          <Pressable style={{ flex: 1, backgroundColor: colors.scrim }} onPress={() => setDrawerOpen(false)} />
        </View>
      )}
      <View style={{ flex: 1 }}>
        <View style={{
          flexDirection: "row", alignItems: "center", gap: space.md, paddingHorizontal: space.xl,
          paddingTop: insets.top + space.lg, paddingBottom: space.lg, borderBottomWidth: 1, borderBottomColor: colors.border,
          backgroundColor: colors.bg,
        }}>
          {!isDesktop && (
            <Pressable testID="admin-menu-toggle" onPress={() => setDrawerOpen(true)} hitSlop={8}>
              <Ionicons name="menu" size={22} color={colors.ink} />
            </Pressable>
          )}
          {icon && (
            <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: colors.ink, alignItems: "center", justifyContent: "center" }}>
              <Ionicons name={icon} size={18} color={colors.bg} />
            </View>
          )}
          <View style={{ flex: 1 }}>
            <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 19, letterSpacing: -0.3 }}>{title}</Text>
            {subtitle ? <Text style={{ color: colors.faint, fontFamily: fonts.bodyMedium, fontSize: 12.5 }}>{subtitle}</Text> : null}
          </View>
        </View>
        <ScrollView contentContainerStyle={{ padding: space.xl, gap: space.lg }}>{children}</ScrollView>
      </View>
    </View>
  );
}
