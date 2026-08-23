import React, { useCallback, useEffect, useState } from "react";
import { Alert, Switch, Text, View } from "react-native";

import { adminApi } from "@/src/admin-api";
import { Badge } from "@/src/components/admin/Badge";
import { fonts } from "@/src/hooks/use-app-fonts";
import { radius, space, useTheme } from "@/src/theme";

type Flag = { key: string; enabled: boolean; description?: string; updated_at?: string };

export default function AdminFeatureFlags() {
  const { colors } = useTheme();
  const [flags, setFlags] = useState<Flag[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    adminApi.get("/admin/feature-flags").then(setFlags).catch(() => {}).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const toggle = async (key: string, enabled: boolean) => {
    try {
      await adminApi.patch(`/admin/feature-flags/${key}`, { enabled });
      load();
    } catch (e: any) {
      Alert.alert("Ops", e.message || "Não foi possível alterar.");
    }
  };

  if (loading) return null;

  return (
    <View style={{ gap: space.md, maxWidth: 640 }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
        <Badge label="SENSÍVEL" tone="amber" />
        <Text style={{ flex: 1, color: colors.faint, fontFamily: fonts.body, fontSize: 12, lineHeight: 16 }}>
          Ativa ou desativa funcionalidades do aplicativo em tempo real, sem precisar publicar uma nova versão. Toda alteração fica registrada na auditoria.
        </Text>
      </View>
      {flags.map((f) => (
        <View key={f.key} style={{ flexDirection: "row", alignItems: "center", gap: space.md, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: space.lg }}>
          <View style={{ flex: 1 }}>
            <Text style={{ color: colors.ink, fontFamily: fonts.bodyBold, fontSize: 14 }}>{f.key}</Text>
            {f.description ? <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 12, marginTop: 2 }}>{f.description}</Text> : null}
          </View>
          <Switch testID={`admin-flag-${f.key}`} value={f.enabled} onValueChange={(v) => toggle(f.key, v)} trackColor={{ true: colors.primary }} />
        </View>
      ))}
    </View>
  );
}
