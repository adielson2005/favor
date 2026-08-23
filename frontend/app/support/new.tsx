import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import { Alert, Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { Btn, Chip, Field } from "@/src/components/ui";
import { useRequireAuth } from "@/src/hooks/use-require-auth";
import { useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

const CATEGORIES = [
  { value: "BUG", label: "Bug" }, { value: "IDEIA", label: "Ideia" }, { value: "SUGESTAO", label: "Sugestão" },
  { value: "RECLAMACAO", label: "Reclamação" }, { value: "PAGAMENTO", label: "Pagamento" }, { value: "CONTA", label: "Conta" },
  { value: "SEGURANCA", label: "Segurança" }, { value: "OUTRO", label: "Outro" },
];

export default function SupportNew() {
  const { colors } = useTheme();
  useRequireAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [category, setCategory] = useState<string | null>(null);
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);

  const canSubmit = !!category && subject.trim().length >= 3 && description.trim().length > 0;

  const submit = async () => {
    if (!canSubmit) return;
    setBusy(true);
    try {
      const ticket = await api.post("/tickets", { category, subject: subject.trim(), description: description.trim() });
      router.replace(`/support/${ticket.id}`);
    } catch (e: any) {
      Alert.alert("Ops", e.message || "Não foi possível abrir o chamado.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + 8 }}>
      <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: 20, height: 48, gap: 14 }}>
        <Pressable onPress={() => safeBack(router, "/support")} hitSlop={10}><Ionicons name="arrow-back" size={24} color={colors.ink} /></Pressable>
        <Text style={{ color: colors.ink, fontSize: 18, fontWeight: "800" }}>Novo chamado</Text>
      </View>

      <ScrollView contentContainerStyle={{ padding: 20, gap: 18 }} keyboardShouldPersistTaps="handled">
        <View style={{ gap: 10 }}>
          <Text style={{ color: colors.muted, fontSize: 13, fontWeight: "700" }}>Categoria</Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            {CATEGORIES.map((c) => (
              <Chip key={c.value} testID={`support-category-${c.value}`} label={c.label} active={category === c.value} onPress={() => setCategory(c.value)} />
            ))}
          </View>
        </View>

        <Field label="Assunto" value={subject} onChangeText={setSubject} placeholder="Resuma em poucas palavras" maxLength={140} testID="support-subject-input" />
        <Field
          label="Descrição"
          value={description}
          onChangeText={setDescription}
          placeholder="Conte com detalhes o que aconteceu ou o que você gostaria de sugerir"
          multiline
          maxLength={4000}
          style={{ minHeight: 140, textAlignVertical: "top" }}
          testID="support-description-input"
        />

        <Btn title="Enviar chamado" onPress={submit} disabled={!canSubmit || busy} loading={busy} testID="support-submit-button" />
      </ScrollView>
    </View>
  );
}
