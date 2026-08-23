import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { Alert, FlatList, KeyboardAvoidingView, Platform, Pressable, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useRequireAuth } from "@/src/hooks/use-require-auth";
import { useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

type Message = { id: string; author_type: "user" | "admin"; author_id: string; text: string; created_at: string };
type Ticket = {
  id: string; category: string; subject: string; status: string; messages: Message[]; created_at: string;
};

const STATUS_LABELS: Record<string, string> = {
  OPEN: "Aberto", IN_PROGRESS: "Em andamento", WAITING_USER: "Aguardando você", RESOLVED: "Resolvido", CLOSED: "Fechado",
};

export default function SupportThread() {
  const { colors } = useTheme();
  useRequireAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { id } = useLocalSearchParams<{ id: string }>();

  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const listRef = useRef<FlatList>(null);
  const poll = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.get(`/tickets/${id}`);
      setTicket(data);
    } catch { /* keep last state */ }
  }, [id]);

  useFocusEffect(useCallback(() => {
    load();
    poll.current = setInterval(load, 5000);
    return () => { if (poll.current) clearInterval(poll.current); };
  }, [load]));

  useEffect(() => {
    setTimeout(() => listRef.current?.scrollToEnd({ animated: false }), 80);
  }, [ticket?.messages.length]);

  const send = async () => {
    if (!text.trim()) return;
    const body = text.trim();
    setText("");
    setSending(true);
    try {
      await api.post(`/tickets/${id}/messages`, { text: body });
      await load();
    } catch (e: any) {
      Alert.alert("Ops", e.message || "Não foi possível enviar.");
    } finally {
      setSending(false);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + 8 }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 20, paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: colors.border }}>
        <Pressable onPress={() => safeBack(router, "/support")} hitSlop={10}><Ionicons name="arrow-back" size={24} color={colors.ink} /></Pressable>
        <View style={{ flex: 1 }}>
          <Text style={{ color: colors.ink, fontSize: 15, fontWeight: "800" }} numberOfLines={1}>{ticket?.subject || "Chamado"}</Text>
          <Text style={{ color: colors.muted, fontSize: 12 }}>{ticket ? (STATUS_LABELS[ticket.status] || ticket.status) : ""}</Text>
        </View>
      </View>

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined} keyboardVerticalOffset={0}>
        <FlatList
          ref={listRef}
          data={ticket?.messages || []}
          keyExtractor={(item) => item.id}
          contentContainerStyle={{ padding: 20, gap: 10, flexGrow: 1 }}
          renderItem={({ item }) => {
            const mine = item.author_type === "user";
            return (
              <View style={{ alignSelf: mine ? "flex-end" : "flex-start", maxWidth: "80%" }}>
                <View style={{ backgroundColor: mine ? colors.primary : colors.surface, borderWidth: mine ? 0 : 1, borderColor: colors.border, borderRadius: 18, borderBottomRightRadius: mine ? 5 : 18, borderBottomLeftRadius: mine ? 18 : 5, paddingHorizontal: 14, paddingVertical: 10 }}>
                  <Text style={{ color: mine ? colors.onPrimary : colors.ink, fontSize: 14, lineHeight: 20 }}>{item.text}</Text>
                </View>
                <Text style={{ color: colors.faint, fontSize: 10, marginTop: 4, marginHorizontal: 4, textAlign: mine ? "right" : "left" }}>
                  {mine ? "Você" : "Equipe fazum"} · {new Date(item.created_at).toLocaleString("pt-BR")}
                </Text>
              </View>
            );
          }}
        />

        {ticket && ["RESOLVED", "CLOSED"].includes(ticket.status) && (
          <View style={{ marginHorizontal: 16, marginBottom: 8, padding: 10, borderRadius: 12, backgroundColor: colors.alt }}>
            <Text style={{ color: colors.muted, fontSize: 12, textAlign: "center" }}>
              Este chamado foi {ticket.status === "RESOLVED" ? "resolvido" : "fechado"}. Responder abaixo reabre o chamado.
            </Text>
          </View>
        )}

        <View style={{ flexDirection: "row", alignItems: "flex-end", gap: 8, paddingHorizontal: 16, paddingTop: 10, paddingBottom: Math.max(insets.bottom, 12), borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.bg }}>
          <TextInput
            testID="support-thread-input"
            value={text}
            onChangeText={setText}
            placeholder="Escreva uma mensagem..."
            placeholderTextColor={colors.faint}
            multiline
            style={{ flex: 1, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 22, paddingHorizontal: 16, paddingTop: 12, paddingBottom: 12, color: colors.ink, fontSize: 14, maxHeight: 110 }}
          />
          <Pressable
            testID="support-thread-send-button"
            onPress={send}
            disabled={sending || !text.trim()}
            style={({ pressed }) => [{ width: 44, height: 44, borderRadius: 22, backgroundColor: text.trim() ? colors.primary : colors.alt, alignItems: "center", justifyContent: "center", opacity: pressed ? 0.8 : 1 }]}
          >
            <Ionicons name="send" size={17} color={text.trim() ? colors.onPrimary : colors.faint} />
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}
