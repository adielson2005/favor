import { Ionicons } from "@expo/vector-icons";
import { Slot, useRouter, useSegments } from "expo-router";
import React, { useEffect } from "react";
import { ActivityIndicator, View } from "react-native";

import { AdminAuthProvider, useAdminAuth } from "@/src/admin-auth";
import { AdminShell } from "@/src/components/admin/AdminShell";
import { light, ThemeContext, useTheme } from "@/src/theme";

const META: Record<string, { title: string; subtitle: string; icon: React.ComponentProps<typeof Ionicons>["name"] }> = {
  admin: { title: "Dashboard", subtitle: "Visão geral da operação", icon: "grid-outline" },
  supervision: { title: "Supervisão", subtitle: "Quem está online e o que mudou", icon: "eye-outline" },
  users: { title: "Usuários", subtitle: "Contas cadastradas no app", icon: "people-outline" },
  orders: { title: "Pedidos", subtitle: "Favores e serviços publicados", icon: "briefcase-outline" },
  payments: { title: "Pagamentos", subtitle: "Cobranças processadas", icon: "card-outline" },
  withdrawals: { title: "Saques", subtitle: "Solicitações de retirada", icon: "cash-outline" },
  disputes: { title: "Disputas", subtitle: "Conflitos entre usuários", icon: "warning-outline" },
  reports: { title: "Denúncias", subtitle: "Relatos da comunidade", icon: "flag-outline" },
  support: { title: "Suporte", subtitle: "Chamados e feedback", icon: "chatbox-ellipses-outline" },
  security: { title: "Segurança", subtitle: "Sinalizações de risco e eventos", icon: "shield-outline" },
  categories: { title: "Categorias", subtitle: "Tipos de favor e serviço", icon: "pricetags-outline" },
  locations: { title: "Localidades", subtitle: "Cidades e bairros atendidos", icon: "location-outline" },
  "feature-flags": { title: "Feature flags", subtitle: "Recursos ativos no app", icon: "flag-outline" },
  notifications: { title: "Notificações", subtitle: "Avisos para os usuários", icon: "megaphone-outline" },
  config: { title: "Configurações", subtitle: "Regras financeiras", icon: "settings-outline" },
  audit: { title: "Auditoria", subtitle: "Histórico de ações administrativas", icon: "document-text-outline" },
  team: { title: "Equipe", subtitle: "Administradores com acesso", icon: "shield-checkmark-outline" },
};

function Gate() {
  const { colors } = useTheme();
  const router = useRouter();
  const segments = useSegments();
  const { ready, admin } = useAdminAuth();
  const onLoginScreen = segments[segments.length - 1] === "login";

  useEffect(() => {
    if (!ready) return;
    if (!admin && !onLoginScreen) router.replace("/admin/login");
    if (admin && onLoginScreen) router.replace("/admin");
  }, [ready, admin, onLoginScreen, router]);

  if (!ready) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  if (onLoginScreen) return <Slot />;
  if (!admin) return null; // redirecting

  const routeKey = segments[1] || "admin";
  const meta = META[routeKey] || { title: "Painel", subtitle: "", icon: "grid-outline" as const };
  return <AdminShell title={meta.title} subtitle={meta.subtitle} icon={meta.icon}><Slot /></AdminShell>;
}

// The admin panel always renders in light mode, regardless of the consumer app's
// theme preference — staff use it as a work tool, not something that should follow
// whatever a shared/kiosk device happens to have set. Scoped to this subtree only
// (a local ThemeContext override) so the consumer app's own dark mode is untouched.
export default function AdminLayout() {
  return (
    <ThemeContext.Provider value={{ colors: light, isDark: false, pref: "light", setPref: () => {} }}>
      <AdminAuthProvider>
        <Gate />
      </AdminAuthProvider>
    </ThemeContext.Provider>
  );
}
