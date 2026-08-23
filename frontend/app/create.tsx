import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import * as ImagePicker from "expo-image-picker";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useEffect, useMemo, useState } from "react";
import { Alert, Image, KeyboardAvoidingView, Linking, Platform, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import Animated, { FadeIn, FadeOut } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { Btn, Chip, Field } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useFeatureFlag } from "@/src/hooks/use-feature-flags";
import { useRequireAuth } from "@/src/hooks/use-require-auth";
import { useApp } from "@/src/state";
import { type, useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

const MAX_PHOTOS = 4;

const EXTRA_FIELDS: Record<string, { key: string; label: string; placeholder: string }[]> = {
  "cat-entregas": [
    { key: "origem", label: "De onde?", placeholder: "Ex: Correios do centro" },
    { key: "destino", label: "Para onde?", placeholder: "Ex: Rua B, Cidade Nova" },
  ],
  "cat-compras": [{ key: "local_compra", label: "Onde comprar?", placeholder: "Ex: Supermercado do bairro" }],
  "cat-casa": [{ key: "ambiente", label: "Qual ambiente ou item?", placeholder: "Ex: Guarda-roupa de 6 portas" }],
  "cat-tecnologia": [{ key: "equipamento", label: "Qual equipamento?", placeholder: "Ex: Notebook Dell" }],
  "cat-veiculos": [{ key: "veiculo", label: "Qual veículo?", placeholder: "Ex: Honda CG 160" }],
  "cat-pets": [{ key: "pet", label: "Sobre o pet", placeholder: "Ex: Golden retriever, dócil" }],
  "cat-documentos": [{ key: "documento", label: "Qual documento?", placeholder: "Ex: Envelope lacrado" }],
  "cat-eventos": [{ key: "evento", label: "Qual evento?", placeholder: "Ex: Aniversário no salão de festas" }],
  "cat-profissionais": [{ key: "prazo", label: "Prazo", placeholder: "Ex: Até sexta-feira" }],
};

const DATES = ["Hoje", "Amanhã", "Esta semana", "A combinar"];
const RECURRENCE_OPTIONS: { key: "none" | "weekly" | "biweekly" | "monthly"; label: string }[] = [
  { key: "none", label: "Não se repete" }, { key: "weekly", label: "Semanal" },
  { key: "biweekly", label: "Quinzenal" }, { key: "monthly", label: "Mensal" },
];

export default function Create() {
  const { colors } = useTheme();
  const { categories, neighborhoods, city } = useApp();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { orderId, prefillFrom } = useLocalSearchParams<{ orderId?: string; prefillFrom?: string }>();
  const isEdit = !!orderId;
  useRequireAuth();
  const urgentServicesEnabled = useFeatureFlag("URGENT_SERVICES");
  const recurringServicesEnabled = useFeatureFlag("RECURRING_SERVICES");

  const [step, setStep] = useState(0);
  const [loadingOrder, setLoadingOrder] = useState(isEdit || !!prefillFrom);
  const [title, setTitle] = useState("");
  const [type, setType] = useState<"favor" | "servico">("favor");
  const [categoryId, setCategoryId] = useState<string | null>(null);
  const [subcategoryId, setSubcategoryId] = useState<string | null>(null);
  const [description, setDescription] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [photos, setPhotos] = useState<string[]>([]);
  const [hoodId, setHoodId] = useState<string | null>(null);
  const [hoodSearch, setHoodSearch] = useState("");
  const [dateLabel, setDateLabel] = useState("Hoje");
  const [timeLabel, setTimeLabel] = useState("");
  const [urgent, setUrgent] = useState(false);
  const [recurrence, setRecurrence] = useState<"none" | "weekly" | "biweekly" | "monthly">("none");
  const [budget, setBudget] = useState("");
  const [publishing, setPublishing] = useState(false);

  useEffect(() => {
    if (!isEdit) return;
    api.get(`/orders/${orderId}`).then((order) => {
      setTitle(order.title); setType(order.type); setCategoryId(order.category_id);
      setSubcategoryId(order.subcategory_id || null); setDescription(order.description || "");
      setFields(order.fields || {}); setPhotos(order.photos || []); setHoodId(order.neighborhood_id || null);
      setDateLabel(order.date_label); setTimeLabel(order.time_label || ""); setBudget(String(order.budget || ""));
      setUrgent(order.urgent || false); setRecurrence(order.recurrence || "none");
    }).catch(() => {
      Alert.alert("Ops", "Não conseguimos carregar esse pedido.");
      safeBack(router, "/(tabs)/home");
    }).finally(() => setLoadingOrder(false));
  }, [isEdit, orderId, router]);

  // Rehire ("Contratar novamente"): prefill from a past order, but never carry over
  // date/budget/photos — those need to be decided fresh for the new request.
  useEffect(() => {
    if (isEdit || !prefillFrom) return;
    api.get(`/orders/${prefillFrom}`).then((order) => {
      setTitle(order.title); setType(order.type); setCategoryId(order.category_id);
      setSubcategoryId(order.subcategory_id || null); setDescription(order.description || "");
      setFields(order.fields || {}); setHoodId(order.neighborhood_id || null);
    }).catch(() => {}).finally(() => setLoadingOrder(false));
  }, [isEdit, prefillFrom]);

  const category = categories.find((c) => c.id === categoryId);
  const extras = categoryId ? EXTRA_FIELDS[categoryId] || [] : [];
  const filteredHoods = useMemo(
    () => neighborhoods.filter((n) => n.name.toLowerCase().includes(hoodSearch.toLowerCase())),
    [neighborhoods, hoodSearch],
  );

  const STEPS = ["need", "category", "details", "photos", "where", "when", "budget"] as const;
  const stepKey = STEPS[step];
  const canContinue = {
    need: title.trim().length >= 3,
    category: !!categoryId,
    details: true,
    photos: true,
    where: !!hoodId,
    when: !!dateLabel,
    budget: Number(budget) > 0,
  }[stepKey];

  const pickPhoto = async () => {
    if (photos.length >= MAX_PHOTOS) return;
    const current = await ImagePicker.getMediaLibraryPermissionsAsync();
    if (!current.granted) {
      if (!current.canAskAgain) {
        Alert.alert("Permissão necessária", "Para adicionar fotos, permita o acesso às imagens nas configurações.", [
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
      setPhotos((p) => [...p, `data:image/jpeg;base64,${result.assets[0].base64}`]);
    }
  };

  const publish = async () => {
    setPublishing(true);
    try {
      if (isEdit) {
        await api.patch(`/orders/${orderId}`, {
          title: title.trim(), description: description.trim(),
          category_id: categoryId, subcategory_id: subcategoryId, neighborhood_id: hoodId,
          date_label: dateLabel, time_label: timeLabel.trim(), budget: Number(budget),
          fields, photos, urgent, recurrence,
        });
        router.replace(`/order/${orderId}`);
      } else {
        const order = await api.post("/orders", {
          title: title.trim(), description: description.trim(), type,
          category_id: categoryId, subcategory_id: subcategoryId,
          city_id: city?.id || "city-parauapebas", neighborhood_id: hoodId,
          date_label: dateLabel, time_label: timeLabel.trim(), budget: Number(budget),
          fields, photos, urgent, recurrence,
        });
        if (Platform.OS !== "web") Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        router.replace(`/order/${order.id}?published=1`);
      }
    } catch (e: any) {
      Alert.alert("Ops", e.message || "Não conseguimos salvar agora. Tente novamente.");
      setPublishing(false);
    }
  };

  const next = () => (step < STEPS.length - 1 ? setStep(step + 1) : publish());
  const back = () => (step > 0 ? setStep(step - 1) : safeBack(router, isEdit ? `/order/${orderId}` : "/(tabs)/home"));

  if (loadingOrder) {
    return <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center" }} />;
  }

  const label = { color: colors.ink, ...type.h1, marginBottom: 6 };
  const hint = { color: colors.muted, ...type.body, marginBottom: 18 };

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: Platform.OS === "ios" ? 12 : insets.top + 8 }}>
      {/* Header */}
      <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: 20, height: 48, gap: 14 }}>
        <Pressable testID="create-close-button" onPress={back} hitSlop={10}>
          <Ionicons name={step === 0 ? "close" : "arrow-back"} size={24} color={colors.ink} />
        </Pressable>
        <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 16, flex: 1 }}>{isEdit ? "Editar pedido" : "Novo pedido"}</Text>
        <Text style={{ color: colors.faint, fontSize: 13, fontWeight: "600" }}>{step + 1}/{STEPS.length}</Text>
      </View>
      <View style={{ height: 3, backgroundColor: colors.alt, marginHorizontal: 20, borderRadius: 2, marginBottom: 8 }}>
        <View style={{ height: 3, borderRadius: 2, backgroundColor: colors.primary, width: `${((step + 1) / STEPS.length) * 100}%` }} />
      </View>

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 20, paddingBottom: 40 }} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
        <Animated.View key={stepKey} entering={FadeIn.duration(180)} exiting={FadeOut.duration(120)}>
          {stepKey === "need" && (
            <View>
              <Text style={label}>O que você precisa?</Text>
              <Text style={hint}>Descreva em poucas palavras.</Text>
              <Field testID="create-title-input" value={title} onChangeText={setTitle} placeholder="Ex: Buscar uma encomenda" autoFocus />
              <View style={{ marginTop: 24, gap: 10 }}>
                {[
                  { key: "favor" as const, title: "Favor", body: "Tarefa simples e pontual", icon: "hand-left-outline" as const },
                  { key: "servico" as const, title: "Serviço", body: "Exige mais tempo ou habilidade", icon: "construct-outline" as const },
                ].map((option) => (
                  <Pressable
                    key={option.key}
                    testID={`type-${option.key}`}
                    disabled={isEdit}
                    onPress={() => setType(option.key)}
                    style={{ flexDirection: "row", alignItems: "center", gap: 14, padding: 16, borderRadius: 16, backgroundColor: colors.surface, borderWidth: 1.5, borderColor: type === option.key ? colors.primary : colors.border, opacity: isEdit && type !== option.key ? 0.5 : 1 }}
                  >
                    <Ionicons name={option.icon} size={20} color={type === option.key ? colors.primary : colors.muted} />
                    <View style={{ flex: 1 }}>
                      <Text style={{ color: colors.ink, fontSize: 15, fontWeight: "700" }}>{option.title}</Text>
                      <Text style={{ color: colors.muted, fontSize: 13 }}>{option.body}</Text>
                    </View>
                    {type === option.key && <Ionicons name="checkmark-circle" size={20} color={colors.primary} />}
                  </Pressable>
                ))}
              </View>
              {isEdit && <Text style={{ color: colors.faint, fontSize: 12, marginTop: 10 }}>O tipo não pode ser alterado depois que o pedido é criado.</Text>}
            </View>
          )}

          {stepKey === "category" && (
            <View>
              <Text style={label}>Qual categoria combina?</Text>
              <Text style={hint}>Isso ajuda os fazedores certos a encontrarem seu pedido.</Text>
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 10 }}>
                {categories.map((cat) => (
                  <Pressable
                    key={cat.id}
                    testID={`create-cat-${cat.id}`}
                    onPress={() => { setCategoryId(cat.id); setSubcategoryId(null); }}
                    style={{ width: "48%", flexGrow: 1, padding: 14, borderRadius: 16, backgroundColor: colors.surface, borderWidth: 1.5, borderColor: categoryId === cat.id ? colors.primary : colors.border, gap: 8 }}
                  >
                    <Ionicons name={cat.icon as keyof typeof Ionicons.glyphMap} size={20} color={categoryId === cat.id ? colors.primary : colors.muted} />
                    <Text style={{ color: colors.ink, fontSize: 13, fontWeight: "700" }}>{cat.name}</Text>
                  </Pressable>
                ))}
              </View>
              {category && category.subcategories.length > 0 && (
                <View style={{ marginTop: 24, gap: 10 }}>
                  <Text style={{ color: colors.muted, fontSize: 12, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.6 }}>Mais específico (opcional)</Text>
                  <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
                    {category.subcategories.map((sub) => (
                      <Chip key={sub.id} label={sub.name} active={subcategoryId === sub.id} onPress={() => setSubcategoryId(subcategoryId === sub.id ? null : sub.id)} />
                    ))}
                  </View>
                </View>
              )}
            </View>
          )}

          {stepKey === "details" && (
            <View style={{ gap: 16 }}>
              <View>
                <Text style={label}>Conte um pouco mais.</Text>
                <Text style={hint}>Detalhes ajudam a receber propostas melhores.</Text>
              </View>
              <Field testID="create-description-input" value={description} onChangeText={setDescription} multiline placeholder="Descreva a tarefa..." style={{ minHeight: 110, textAlignVertical: "top" }} />
              {extras.map((extra) => (
                <Field
                  key={extra.key}
                  label={extra.label}
                  value={fields[extra.key] || ""}
                  onChangeText={(v) => setFields({ ...fields, [extra.key]: v })}
                  placeholder={extra.placeholder}
                />
              ))}
            </View>
          )}

          {stepKey === "photos" && (
            <View>
              <Text style={label}>Quer adicionar fotos?</Text>
              <Text style={hint}>Opcional — ajuda a explicar o que você precisa.</Text>
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 10 }}>
                {photos.map((photo, i) => (
                  <View key={i} style={{ width: 84, height: 84 }}>
                    <Image source={{ uri: photo }} style={{ width: 84, height: 84, borderRadius: 14 }} />
                    <Pressable
                      testID={`remove-photo-${i}`}
                      onPress={() => setPhotos((p) => p.filter((_, idx) => idx !== i))}
                      style={{ position: "absolute", top: -6, right: -6, width: 22, height: 22, borderRadius: 11, backgroundColor: colors.danger, alignItems: "center", justifyContent: "center" }}
                    >
                      <Ionicons name="close" size={13} color="#FFF" />
                    </Pressable>
                  </View>
                ))}
                {photos.length < MAX_PHOTOS && (
                  <Pressable testID="add-photo-button" onPress={pickPhoto} style={{ width: 84, height: 84, borderRadius: 14, borderWidth: 1.5, borderColor: colors.border, borderStyle: "dashed", alignItems: "center", justifyContent: "center", backgroundColor: colors.surface }}>
                    <Ionicons name="camera-outline" size={22} color={colors.muted} />
                  </Pressable>
                )}
              </View>
            </View>
          )}

          {stepKey === "where" && (
            <View>
              <Text style={label}>Onde será?</Text>
              <Text style={hint}>{city?.name || "Parauapebas"}, PA · escolha o bairro</Text>
              <Field testID="create-hood-search" value={hoodSearch} onChangeText={setHoodSearch} placeholder="Buscar bairro..." />
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 16 }}>
                {filteredHoods.map((n) => (
                  <Chip key={n.id} testID={`hood-${n.id}`} label={n.name} active={hoodId === n.id} onPress={() => setHoodId(n.id)} />
                ))}
              </View>
            </View>
          )}

          {stepKey === "when" && (
            <View>
              <Text style={label}>Quando?</Text>
              <Text style={hint}>Escolha o melhor momento.</Text>
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 20 }}>
                {DATES.map((d) => <Chip key={d} testID={`date-${d}`} label={d} active={dateLabel === d} onPress={() => setDateLabel(d)} />)}
              </View>
              <Field label="Horário (opcional)" value={timeLabel} onChangeText={setTimeLabel} placeholder="Ex: até 17:00" />

              {urgentServicesEnabled && (
                <Pressable
                  testID="urgent-toggle"
                  onPress={() => setUrgent(!urgent)}
                  style={{ flexDirection: "row", alignItems: "center", gap: 10, marginTop: 24, padding: 14, borderRadius: 16, borderWidth: 1.5, borderColor: urgent ? colors.danger : colors.border, backgroundColor: urgent ? colors.dangerSoft : colors.surface }}
                >
                  <Ionicons name={urgent ? "flash" : "flash-outline"} size={20} color={urgent ? colors.danger : colors.muted} />
                  <View style={{ flex: 1 }}>
                    <Text style={{ color: colors.ink, fontWeight: "700", fontSize: 14 }}>Preciso agora</Text>
                    <Text style={{ color: colors.muted, fontSize: 12 }}>Destaca seu pedido para quem está por perto.</Text>
                  </View>
                  <Ionicons name={urgent ? "checkmark-circle" : "ellipse-outline"} size={22} color={urgent ? colors.danger : colors.faint} />
                </Pressable>
              )}

              {recurringServicesEnabled && (
                <>
                  <Text style={{ ...label, fontSize: 15, marginTop: 24, marginBottom: 8 }}>Se repete?</Text>
                  <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
                    {RECURRENCE_OPTIONS.map((r) => <Chip key={r.key} testID={`recurrence-${r.key}`} label={r.label} active={recurrence === r.key} onPress={() => setRecurrence(r.key)} />)}
                  </View>
                </>
              )}
            </View>
          )}

          {stepKey === "budget" && (
            <View>
              <Text style={label}>Quanto pretende pagar?</Text>
              <Text style={hint}>Você ainda pode negociar nas propostas.</Text>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginVertical: 10 }}>
                <Text style={{ color: colors.muted, fontSize: 26, fontWeight: "700" }}>R$</Text>
                <TextInput
                  testID="create-budget-input"
                  value={budget}
                  onChangeText={(v) => setBudget(v.replace(/[^0-9]/g, ""))}
                  keyboardType="numeric"
                  placeholder="0"
                  placeholderTextColor={colors.faint}
                  style={{ fontSize: 44, fontWeight: "800", color: colors.ink, minWidth: 120 }}
                />
              </View>
              <View style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 16, padding: 16, marginTop: 16, gap: 6 }}>
                <Text style={{ color: colors.ink, fontSize: 15, fontWeight: "700" }}>{title || "Seu pedido"}</Text>
                <Text style={{ color: colors.muted, fontSize: 13 }}>
                  {category?.name}{subcategoryId ? ` · ${category?.subcategories.find((s) => s.id === subcategoryId)?.name}` : ""} · {type === "favor" ? "Favor" : "Serviço"}
                </Text>
                <Text style={{ color: colors.muted, fontSize: 13 }}>
                  {neighborhoods.find((n) => n.id === hoodId)?.name} · {dateLabel}{timeLabel ? ` · ${timeLabel}` : ""}
                </Text>
              </View>
            </View>
          )}
        </Animated.View>
        </ScrollView>

        {/* Fixed footer — outside the ScrollView */}
        <View style={{ flexDirection: "row", gap: 12, paddingHorizontal: 20, paddingTop: 12, paddingBottom: Math.max(insets.bottom, 16), borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.bg }}>
          <View style={{ flex: 1 }}>
            <Btn title={step === 0 ? "Cancelar" : "Voltar"} variant="ghost" onPress={back} />
          </View>
          <View style={{ flex: 2 }}>
            <Btn
              testID="create-continue-button"
              title={step === STEPS.length - 1 ? (isEdit ? "Salvar alterações" : "Publicar pedido") : "Continuar"}
              icon={step === STEPS.length - 1 ? "checkmark" : "arrow-forward"}
              onPress={next}
              disabled={!canContinue}
              loading={publishing}
            />
          </View>
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}
