import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Alert, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Animated, { FadeIn, FadeInDown, ZoomIn } from "react-native-reanimated";

import { api, City, Neighborhood, StateRef } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Btn, Chip, Field } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { extractIdToken, useGoogleAuth } from "@/src/hooks/use-google-auth";
import { useBreakpoint } from "@/src/hooks/use-breakpoint";
import { radius, space, type, useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

const STEPS = ["nome", "email", "senha", "local", "preferencia"] as const;

const PREFERENCES = [
  { key: "client" as const, icon: "hand-left-outline" as const, title: "Preciso de ajuda", body: "Quero publicar tarefas para outras pessoas fazerem." },
  { key: "worker" as const, icon: "briefcase-outline" as const, title: "Quero fazer serviços", body: "Quero encontrar trabalhos perto de mim." },
  { key: "both" as const, icon: "swap-horizontal-outline" as const, title: "Quero os dois", body: "Vou pedir ajuda e também fazer trabalhos." },
];

function passwordStrength(pw: string): { label: string; score: number; color: "danger" | "amber" | "green" } {
  let score = 0;
  if (pw.length >= 8) score++;
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score++;
  if (/\d/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  if (score <= 1) return { label: "Fraca", score, color: "danger" };
  if (score <= 2) return { label: "Média", score, color: "amber" };
  return { label: "Forte", score, color: "green" };
}

export default function Signup() {
  const { colors } = useTheme();
  const { register, loginWithGoogle } = useAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const google = useGoogleAuth();
  const { isDesktop } = useBreakpoint();

  const [step, setStep] = useState(0);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [states, setStates] = useState<StateRef[]>([]);
  const [cities, setCities] = useState<City[]>([]);
  const [neighborhoods, setNeighborhoods] = useState<Neighborhood[]>([]);
  const [stateId, setStateId] = useState<string | null>(null);
  const [cityId, setCityId] = useState<string | null>(null);
  const [hoodId, setHoodId] = useState<string | null>(null);
  const [hoodSearch, setHoodSearch] = useState("");
  const [preference, setPreference] = useState<"client" | "worker" | "both" | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [createdName, setCreatedName] = useState("");
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    api.get("/geo/states").then((data: StateRef[]) => {
      setStates(data);
      if (data.length === 1) setStateId(data[0].id);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!stateId) { setCities([]); return; }
    api.get(`/geo/cities?state_id=${stateId}`).then((data: City[]) => {
      setCities(data);
      if (data.length === 1) setCityId(data[0].id);
    }).catch(() => {});
  }, [stateId]);

  useEffect(() => {
    if (!cityId) { setNeighborhoods([]); return; }
    api.get(`/geo/neighborhoods?city_id=${cityId}`).then(setNeighborhoods).catch(() => {});
  }, [cityId]);

  const filteredHoods = useMemo(
    () => neighborhoods.filter((n) => n.name.toLowerCase().includes(hoodSearch.toLowerCase())),
    [neighborhoods, hoodSearch],
  );

  const strength = useMemo(() => passwordStrength(password), [password]);
  const stepKey = STEPS[step];
  const canContinue =
    stepKey === "nome" ? firstName.trim().length >= 2 :
    stepKey === "email" ? /\S+@\S+\.\S+/.test(email) :
    stepKey === "senha" ? password.length >= 8 && /[a-z]/i.test(password) && /\d/.test(password) && password === confirmPassword :
    stepKey === "local" ? !!cityId :
    !!preference;

  const hasProgress = firstName.trim() || lastName.trim() || email.trim() || password;

  const back = () => {
    if (step > 0) { setStep(step - 1); return; }
    if (hasProgress) {
      Alert.alert("Você ainda não terminou seu cadastro.", "Quer continuar depois?", [
        { text: "Continuar cadastro", style: "cancel" },
        { text: "Sair", style: "destructive", onPress: () => safeBack(router, "/auth/welcome") },
      ]);
    } else {
      safeBack(router, "/auth/welcome");
    }
  };

  const submit = async () => {
    setSubmitting(true);
    const name = `${firstName.trim()} ${lastName.trim()}`.trim();
    try {
      await register({ name, email: email.trim().toLowerCase(), password, city_id: cityId!, neighborhood_id: hoodId, preference: preference! });
      setCreatedName(firstName.trim());
      setSuccess(true);
    } catch (e: any) {
      Alert.alert("Não foi possível criar sua conta", e.message || "Tente novamente.");
    } finally {
      setSubmitting(false);
    }
  };

  const next = () => (step < STEPS.length - 1 ? setStep(step + 1) : submit());

  useEffect(() => {
    if (!success) return;
    const t = setTimeout(() => router.replace("/"), 1600);
    return () => clearTimeout(t);
  }, [success, router]);

  useEffect(() => {
    const idToken = extractIdToken(google.response);
    if (!idToken) return;
    (async () => {
      setGoogleLoading(true);
      try {
        await loginWithGoogle(idToken, cityId || "city-parauapebas");
        router.replace("/");
      } catch (e: any) {
        Alert.alert("Não foi possível continuar com o Google", e.message || "Tente novamente.");
      } finally {
        setGoogleLoading(false);
      }
    })();
  }, [google.response, loginWithGoogle, router, cityId]);

  const pressGoogle = () => {
    if (!google.configured) {
      Alert.alert("Google ainda não configurado", "Defina EXPO_PUBLIC_GOOGLE_CLIENT_ID (frontend) e GOOGLE_CLIENT_ID (backend) para ativar.");
      return;
    }
    google.promptAsync();
  };

  const label = { color: colors.ink, ...type.h1, marginBottom: 6 };
  const hint = { color: colors.muted, ...type.body, marginBottom: space.xl };

  if (success) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", gap: space.lg, padding: space.xl }}>
        <Animated.View entering={ZoomIn.duration(360)} style={{ width: 84, height: 84, borderRadius: 42, backgroundColor: colors.greenSoft, alignItems: "center", justifyContent: "center" }}>
          <Ionicons name="checkmark" size={42} color={colors.green} />
        </Animated.View>
        <Animated.View entering={FadeIn.duration(300).delay(150)} style={{ alignItems: "center", gap: space.xs }}>
          <Text style={{ color: colors.ink, ...type.h1, textAlign: "center" }}>Pronto, {createdName}.</Text>
          <Text style={{ color: colors.muted, ...type.body, textAlign: "center" }}>Seu fazum está pronto.</Text>
        </Animated.View>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: isDesktop ? "center" : undefined, justifyContent: isDesktop ? "center" : undefined, padding: isDesktop ? space.xxxl : 0 }}>
    <View style={
      isDesktop
        ? { width: "100%", maxWidth: 560, maxHeight: 680, backgroundColor: colors.surface, borderRadius: radius.xl, borderWidth: 1, borderColor: colors.border, overflow: "hidden" }
        : { flex: 1, paddingTop: Platform.OS === "ios" ? 12 : insets.top + 8 }
    }>
      <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: space.xl, height: 48, gap: space.lg, marginTop: isDesktop ? space.lg : 0 }}>
        <Pressable testID="signup-back-button" onPress={back} hitSlop={10}>
          <Ionicons name={step === 0 ? "close" : "arrow-back"} size={24} color={colors.ink} />
        </Pressable>
        <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 16, flex: 1 }}>Criar conta</Text>
        <Text style={{ color: colors.faint, fontFamily: fonts.bodySemiBold, fontSize: 13 }}>{step + 1}/{STEPS.length}</Text>
      </View>
      <View style={{ height: 3, backgroundColor: colors.alt, marginHorizontal: space.xl, borderRadius: 2, marginBottom: space.sm }}>
        <View style={{ height: 3, borderRadius: 2, backgroundColor: colors.primary, width: `${((step + 1) / STEPS.length) * 100}%` }} />
      </View>

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView contentContainerStyle={{ padding: space.xl, paddingBottom: 40 }} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
          {stepKey === "nome" && (
            <Animated.View entering={FadeInDown.duration(220)}>
              <Text style={label}>Como podemos chamar você?</Text>
              <Text style={hint}>Leva menos de um minuto.</Text>
              <View style={{ gap: space.md }}>
                <Field testID="signup-firstname-input" label="Nome" value={firstName} onChangeText={setFirstName} placeholder="Seu nome" autoFocus autoComplete="given-name" />
                <Field testID="signup-lastname-input" label="Sobrenome" value={lastName} onChangeText={setLastName} placeholder="Seu sobrenome (opcional)" autoComplete="family-name" />
              </View>
            </Animated.View>
          )}

          {stepKey === "email" && (
            <Animated.View entering={FadeInDown.duration(220)}>
              <Text style={label}>Como podemos entrar em contato?</Text>
              <Text style={hint}>Usaremos seu e-mail para proteger sua conta e avisar sobre seus pedidos.</Text>
              <Field testID="signup-email-input" label="E-mail" value={email} onChangeText={setEmail} placeholder="voce@email.com" autoCapitalize="none" keyboardType="email-address" autoComplete="email" autoFocus />

              <View style={{ flexDirection: "row", alignItems: "center", gap: space.md, marginVertical: space.xl }}>
                <View style={{ flex: 1, height: 1, backgroundColor: colors.border }} />
                <Text style={{ color: colors.faint, ...type.micro }}>ou</Text>
                <View style={{ flex: 1, height: 1, backgroundColor: colors.border }} />
              </View>

              <Pressable
                testID="signup-google-button"
                onPress={pressGoogle}
                disabled={googleLoading}
                style={({ pressed }) => [{
                  flexDirection: "row", alignItems: "center", justifyContent: "center", gap: space.sm,
                  height: 52, borderRadius: radius.md, borderWidth: 1.5, borderColor: colors.border,
                  backgroundColor: colors.surface, opacity: pressed || googleLoading ? 0.7 : 1,
                }]}
              >
                {googleLoading ? <ActivityIndicator color={colors.ink} size="small" /> : (
                  <>
                    <Ionicons name="logo-google" size={18} color={colors.ink} />
                    <Text style={{ color: colors.ink, fontFamily: fonts.bodyBold, fontSize: 15 }}>Continuar com Google</Text>
                  </>
                )}
              </Pressable>
            </Animated.View>
          )}

          {stepKey === "senha" && (
            <Animated.View entering={FadeInDown.duration(220)}>
              <Text style={label}>Crie uma senha segura.</Text>
              <Text style={hint}>Só você vai saber ela.</Text>
              <View style={{ gap: space.md }}>
                <Field testID="signup-password-input" label="Senha" value={password} onChangeText={setPassword} placeholder="Mínimo 8 caracteres" secureTextEntry autoFocus autoComplete="new-password" />
                {!!password && (
                  <View style={{ gap: 6 }}>
                    <View style={{ flexDirection: "row", gap: 4 }}>
                      {[0, 1, 2, 3].map((i) => (
                        <View key={i} style={{ flex: 1, height: 4, borderRadius: 2, backgroundColor: i < strength.score ? colors[strength.color] : colors.alt }} />
                      ))}
                    </View>
                    <Text style={{ color: colors[strength.color], fontFamily: fonts.bodySemiBold, fontSize: 12 }}>{strength.label}</Text>
                  </View>
                )}
                <Field testID="signup-confirm-input" label="Confirmar senha" value={confirmPassword} onChangeText={setConfirmPassword} placeholder="Repita a senha" secureTextEntry autoComplete="new-password" />
                <View style={{ gap: 4, marginTop: space.xs }}>
                  <Requirement met={password.length >= 8} label="8 caracteres ou mais" />
                  <Requirement met={/[a-z]/i.test(password)} label="uma letra" />
                  <Requirement met={/\d/.test(password)} label="um número" />
                </View>
              </View>
            </Animated.View>
          )}

          {stepKey === "local" && (
            <Animated.View entering={FadeInDown.duration(220)}>
              <Text style={label}>Onde você está?</Text>
              <Text style={hint}>Usamos isso para mostrar pedidos e trabalhos perto de você.</Text>
              {states.length > 1 && (
                <View style={{ marginBottom: space.lg }}>
                  <Text style={{ color: colors.muted, fontFamily: fonts.bodyBold, fontSize: 12, textTransform: "uppercase", letterSpacing: 0.6, marginBottom: space.sm }}>Estado</Text>
                  <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
                    {states.map((s) => <Chip key={s.id} label={s.uf} active={stateId === s.id} onPress={() => { setStateId(s.id); setCityId(null); setHoodId(null); }} />)}
                  </View>
                </View>
              )}
              {stateId && cities.length > 1 && (
                <View style={{ marginBottom: space.lg }}>
                  <Text style={{ color: colors.muted, fontFamily: fonts.bodyBold, fontSize: 12, textTransform: "uppercase", letterSpacing: 0.6, marginBottom: space.sm }}>Cidade</Text>
                  <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
                    {cities.map((c) => <Chip key={c.id} label={c.name} active={cityId === c.id} onPress={() => { setCityId(c.id); setHoodId(null); }} />)}
                  </View>
                </View>
              )}
              {cityId && (
                <View>
                  <Text style={{ color: colors.muted, fontFamily: fonts.bodyBold, fontSize: 12, textTransform: "uppercase", letterSpacing: 0.6, marginBottom: space.sm }}>Bairro</Text>
                  <Field testID="signup-hood-search" value={hoodSearch} onChangeText={setHoodSearch} placeholder="Buscar bairro (opcional)" />
                  <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm, marginTop: space.lg }}>
                    {filteredHoods.map((n) => (
                      <Chip key={n.id} testID={`signup-hood-${n.id}`} label={n.name} active={hoodId === n.id} onPress={() => setHoodId(hoodId === n.id ? null : n.id)} />
                    ))}
                  </View>
                </View>
              )}
            </Animated.View>
          )}

          {stepKey === "preferencia" && (
            <Animated.View entering={FadeInDown.duration(220)}>
              <Text style={label}>O que você quer fazer no fazum?</Text>
              <Text style={hint}>Isso só personaliza sua primeira experiência — você pode fazer os dois a qualquer momento.</Text>
              <View style={{ gap: space.md }}>
                {PREFERENCES.map((p) => {
                  const active = preference === p.key;
                  return (
                    <Pressable
                      key={p.key}
                      testID={`signup-preference-${p.key}`}
                      onPress={() => setPreference(p.key)}
                      style={{
                        flexDirection: "row", alignItems: "center", gap: space.md, padding: space.lg, borderRadius: radius.lg,
                        borderWidth: active ? 2 : 1.5, borderColor: active ? colors.primary : colors.border,
                        backgroundColor: active ? colors.primarySoft : colors.surface,
                      }}
                    >
                      <View style={{ width: 44, height: 44, borderRadius: 14, backgroundColor: active ? colors.primary : colors.alt, alignItems: "center", justifyContent: "center" }}>
                        <Ionicons name={p.icon} size={21} color={active ? colors.onPrimary : colors.muted} />
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={{ color: colors.ink, fontFamily: fonts.bodyBold, fontSize: 15 }}>{p.title}</Text>
                        <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 13, marginTop: 2 }}>{p.body}</Text>
                      </View>
                      {active && <Ionicons name="checkmark-circle" size={22} color={colors.primary} />}
                    </Pressable>
                  );
                })}
              </View>
            </Animated.View>
          )}
        </ScrollView>

        <View style={{ flexDirection: "row", gap: space.md, paddingHorizontal: space.xl, paddingTop: space.md, paddingBottom: isDesktop ? space.lg : Math.max(insets.bottom, space.lg), borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: isDesktop ? colors.surface : colors.bg }}>
          <View style={{ flex: 1 }}>
            <Btn title={step === 0 ? "Cancelar" : "Voltar"} variant="ghost" onPress={back} />
          </View>
          <View style={{ flex: 2 }}>
            <Btn
              testID="signup-continue-button"
              title={submitting ? "Criando conta..." : step === STEPS.length - 1 ? "Criar conta" : "Continuar"}
              icon={step === STEPS.length - 1 ? "checkmark" : "arrow-forward"}
              onPress={next}
              disabled={!canContinue || submitting}
              loading={submitting}
            />
          </View>
        </View>
      </KeyboardAvoidingView>
    </View>
    </View>
  );
}

function Requirement({ met, label }: { met: boolean; label: string }) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
      <Ionicons name={met ? "checkmark-circle" : "ellipse-outline"} size={14} color={met ? colors.green : colors.faint} />
      <Text style={{ color: met ? colors.ink : colors.faint, fontSize: 12 }}>{label}</Text>
    </View>
  );
}
