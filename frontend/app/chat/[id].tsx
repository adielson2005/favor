import { Ionicons } from "@expo/vector-icons";
import * as ImagePicker from "expo-image-picker";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { Alert, FlatList, Image, KeyboardAvoidingView, Linking, Platform, Pressable, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Message, Order } from "@/src/api";
import { Avatar } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useApp } from "@/src/state";
import { useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

export default function Chat() {
  const { colors } = useTheme();
  const { me } = useApp();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { id } = useLocalSearchParams<{ id: string }>();

  const [order, setOrder] = useState<Order | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const listRef = useRef<FlatList>(null);
  const poll = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const [orderData, messagesData] = await Promise.all([
        api.get(`/orders/${id}`),
        api.get(`/orders/${id}/messages`),
      ]);
      setOrder(orderData);
      setMessages(messagesData);
    } catch { /* keep last state */ }
  }, [id]);

  useFocusEffect(useCallback(() => {
    load();
    poll.current = setInterval(load, 4000);
    return () => { if (poll.current) clearInterval(poll.current); };
  }, [load]));

  useEffect(() => {
    setTimeout(() => listRef.current?.scrollToEnd({ animated: false }), 80);
  }, [messages.length]);

  const send = async (imageB64?: string) => {
    if (!imageB64 && !text.trim()) return;
    const body = { text: text.trim(), image_b64: imageB64 };
    setText("");
    setSending(true);
    try {
      await api.post(`/orders/${id}/messages`, body);
      await load();
    } catch (e: any) { Alert.alert("Ops", e.message); } finally { setSending(false); }
  };

  const pickImage = async () => {
    const current = await ImagePicker.getMediaLibraryPermissionsAsync();
    if (!current.granted) {
      if (!current.canAskAgain) {
        Alert.alert("Permissão necessária", "Para enviar fotos, permita o acesso às imagens nas configurações.", [
          { text: "Agora não" },
          { text: "Abrir configurações", onPress: () => Linking.openSettings() },
        ]);
        return;
      }
      const asked = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!asked.granted) return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], quality: 0.4, base64: true, allowsEditing: true });
    if (!result.canceled && result.assets[0]?.base64) {
      send(`data:image/jpeg;base64,${result.assets[0].base64}`);
    }
  };

  const other = order && me ? (order.client_id === me.id ? order.worker : order.client) : null;

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + 8 }}>
      {/* Header */}
      <View style={{ flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 20, paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: colors.border }}>
        <Pressable testID="chat-back-button" onPress={() => safeBack(router, "/(tabs)/messages")} hitSlop={10}><Ionicons name="arrow-back" size={24} color={colors.ink} /></Pressable>
        <Avatar name={other?.name} initials={other?.initials} size={38} />
        <View style={{ flex: 1 }}>
          <Text style={{ color: colors.ink, fontFamily: fonts.headingBold, fontSize: 15 }}>{other?.name || "Conversa"}</Text>
          <Text style={{ color: colors.muted, fontSize: 12 }} numberOfLines={1}>{order?.title}{order ? ` · ${order.status_label}` : ""}</Text>
        </View>
        <Pressable testID="chat-order-button" onPress={() => router.push(`/order/${id}`)} hitSlop={8}>
          <Ionicons name="document-text-outline" size={20} color={colors.primary} />
        </Pressable>
      </View>

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined} keyboardVerticalOffset={0}>
        <FlatList
          ref={listRef}
          data={messages}
          keyExtractor={(item) => item.id}
          contentContainerStyle={{ padding: 20, gap: 10, flexGrow: 1 }}
          renderItem={({ item }) => {
            if (item.type === "system" || item.sender_id === "system") {
              return (
                <View style={{ alignSelf: "center", backgroundColor: colors.alt, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 12 }}>
                  <Text style={{ color: colors.muted, fontSize: 12 }}>{item.text}</Text>
                </View>
              );
            }
            const mine = !!me && item.sender_id === me.id;
            return (
              <View style={{ alignSelf: mine ? "flex-end" : "flex-start", maxWidth: "80%" }}>
                {item.image_b64 ? (
                  <Image source={{ uri: item.image_b64 }} style={{ width: 200, height: 200, borderRadius: 16 }} resizeMode="cover" />
                ) : (
                  <View style={{ backgroundColor: mine ? colors.primary : colors.surface, borderWidth: mine ? 0 : 1, borderColor: colors.border, borderRadius: 18, borderBottomRightRadius: mine ? 5 : 18, borderBottomLeftRadius: mine ? 18 : 5, paddingHorizontal: 14, paddingVertical: 10 }}>
                    <Text style={{ color: mine ? colors.onPrimary : colors.ink, fontSize: 14, lineHeight: 20 }}>{item.text}</Text>
                  </View>
                )}
              </View>
            );
          }}
          ListEmptyComponent={
            <View style={{ flex: 1, alignItems: "center", justifyContent: "center", gap: 6 }}>
              <Ionicons name="chatbubble-ellipses-outline" size={30} color={colors.faint} />
              <Text style={{ color: colors.muted, fontSize: 14 }}>Comecem a combinar os detalhes.</Text>
            </View>
          }
        />

        {/* Composer */}
        <View style={{ flexDirection: "row", alignItems: "flex-end", gap: 8, paddingHorizontal: 16, paddingTop: 10, paddingBottom: Math.max(insets.bottom, 12), borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.bg }}>
          <Pressable testID="chat-image-button" onPress={pickImage} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: colors.alt, alignItems: "center", justifyContent: "center" }}>
            <Ionicons name="image-outline" size={20} color={colors.muted} />
          </Pressable>
          <TextInput
            testID="chat-input"
            value={text}
            onChangeText={setText}
            placeholder="Escreva uma mensagem..."
            placeholderTextColor={colors.faint}
            multiline
            style={{ flex: 1, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 22, paddingHorizontal: 16, paddingTop: 12, paddingBottom: 12, color: colors.ink, fontSize: 14, maxHeight: 110 }}
          />
          <Pressable
            testID="chat-send-button"
            onPress={() => send()}
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
