import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAuth } from "@/src/auth";
import { Brand } from "@/src/components/Logo";
import { Btn, Field } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { extractIdToken, useGoogleAuth } from "@/src/hooks/use-google-auth";
import { useBreakpoint } from "@/src/hooks/use-breakpoint";
import { radius, space, type, useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

const DEMO_ACCOUNTS = [
  { label: "Cliente", email: "marina@fazum.demo" },
  { label: "Fazedor", email: "joao@fazum.demo" },
  { label: "Admin", email: "admin@fazum.demo" },
];
const DEMO_PASSWORD = "faze2024";

export default function Login() {
  const { colors } = useTheme();
  const { login, loginWithGoogle } = useAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const google = useGoogleAuth();
  const { isDesktop } = useBreakpoint();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [showDemo, setShowDemo] = useState(false);

  const submit = async () => {
    if (!email.trim() || !password) return;
    setLoading(true);
    try {
      await login(email, password);
      router.replace("/");
    } catch (e: any) {
      Alert.alert("Não foi possível entrar", e.message || "Confira o e-mail e a senha.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const idToken = extractIdToken(google.response);
    if (!idToken) return;
    (async () => {
      setGoogleLoading(true);
      try {
        await loginWithGoogle(idToken);
        router.replace("/");
      } catch (e: any) {
        Alert.alert("Não foi possível entrar com o Google", e.message || "Tente novamente.");
      } finally {
        setGoogleLoading(false);
      }
    })();
  }, [google.response, loginWithGoogle, router]);

  const pressGoogle = () => {
    if (!google.configured) {
      Alert.alert("Google ainda não configurado", "Defina EXPO_PUBLIC_GOOGLE_CLIENT_ID (frontend) e GOOGLE_CLIENT_ID (backend) para ativar.");
      return;
    }
    google.promptAsync();
  };

  const formFields = (
    <>
      <View style={{ backgroundColor: colors.surface, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, padding: space.xl, gap: space.md }}>
        <Field testID="login-email-input" label="E-mail" value={email} onChangeText={setEmail} placeholder="voce@email.com" autoCapitalize="none" keyboardType="email-address" />
        <Field testID="login-password-input" label="Senha" value={password} onChangeText={setPassword} placeholder="••••••••" secureTextEntry />
        <Pressable testID="login-forgot-password" onPress={() => router.push("/auth/forgot-password")} hitSlop={6} style={{ alignSelf: "flex-end", marginTop: -space.xs }}>
          <Text style={{ color: colors.primary, fontFamily: fonts.bodySemiBold, fontSize: 13 }}>Esqueci minha senha</Text>
        </Pressable>
        <Btn testID="login-submit-button" title={loading ? "Entrando..." : "Entrar"} onPress={submit} disabled={!email.trim() || !password} loading={loading} />
      </View>

      <View style={{ flexDirection: "row", alignItems: "center", gap: space.md, marginVertical: space.xs }}>
        <View style={{ flex: 1, height: 1, backgroundColor: colors.border }} />
        <Text style={{ color: colors.faint, ...type.micro }}>ou continue com</Text>
        <View style={{ flex: 1, height: 1, backgroundColor: colors.border }} />
      </View>

      <Pressable
        testID="login-google-button"
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

      <Pressable testID="login-goto-signup" onPress={() => router.push("/auth/signup")} style={{ marginTop: space.lg, alignItems: "center" }} hitSlop={8}>
        <Text style={{ color: colors.muted, ...type.small }}>
          Ainda não tem conta? <Text style={{ color: colors.primary, fontFamily: fonts.bodyBold }}>Criar conta</Text>
        </Text>
      </Pressable>
    </>
  );

  const demoBlock = (
    <>
      <Pressable testID="login-demo-toggle" onPress={() => setShowDemo(!showDemo)} style={{ alignItems: "center", paddingVertical: space.md }} hitSlop={8}>
        <Text style={{ color: colors.faint, ...type.small }}>{showDemo ? "Ocultar contas demo" : "Ver contas demo"}</Text>
      </Pressable>
      {showDemo && (
        <View style={{ gap: space.sm, backgroundColor: colors.alt, borderRadius: radius.md, padding: space.lg }}>
          <Text style={{ color: colors.faint, ...type.micro }}>Preenche o formulário, senha {DEMO_PASSWORD}</Text>
          <View style={{ flexDirection: "row", gap: space.sm, flexWrap: "wrap" }}>
            {DEMO_ACCOUNTS.map((acc) => (
              <Pressable
                key={acc.email}
                testID={`login-demo-${acc.label.toLowerCase()}`}
                onPress={() => { setEmail(acc.email); setPassword(DEMO_PASSWORD); }}
                style={{ paddingHorizontal: space.md, height: 36, borderRadius: radius.pill, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center" }}
              >
                <Text style={{ color: colors.ink, fontFamily: fonts.bodyBold, fontSize: 13 }}>{acc.label}</Text>
              </Pressable>
            ))}
          </View>
        </View>
      )}
    </>
  );

  // Desktop: OLX-style plain, compact centered card — no full-bleed color banner,
  // no chrome around it (this route sits outside the (tabs) group, so the sidebar
  // never renders here regardless).
  if (isDesktop) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", padding: space.xxxl }}>
        <View style={{ width: "100%", maxWidth: 440, gap: space.md }}>
          <Pressable testID="login-back-button" onPress={() => safeBack(router, "/auth/welcome")} hitSlop={10} style={{ flexDirection: "row", alignItems: "center", gap: 6, marginBottom: space.sm }}>
            <Ionicons name="arrow-back" size={16} color={colors.muted} />
            <Text style={{ color: colors.muted, fontFamily: fonts.bodySemiBold, fontSize: 13 }}>Voltar</Text>
          </Pressable>
          <Brand size={36} />
          <View style={{ marginBottom: space.xs }}>
            <Text style={{ color: colors.ink, ...type.h1, fontSize: 24 }}>Precisou? Alguém faz.</Text>
            <Text style={{ color: colors.muted, ...type.body, marginTop: space.xs }}>Entre para pedir ajuda ou encontrar trabalhos em Parauapebas.</Text>
          </View>
          {formFields}
          {demoBlock}
        </View>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView contentContainerStyle={{ flexGrow: 1 }} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
        {/* Offset header block — breaks the generic flat-centered-form look */}
        <View style={{
          backgroundColor: colors.primary, paddingTop: insets.top + space.md, paddingBottom: space.xxxl + space.lg,
          paddingHorizontal: space.xl, borderBottomLeftRadius: radius.xl, borderBottomRightRadius: radius.xl,
        }}>
          <Pressable testID="login-back-button" onPress={() => safeBack(router, "/auth/welcome")} hitSlop={10} style={{ width: 36, height: 36, alignItems: "center", justifyContent: "center", marginLeft: -8, marginBottom: space.lg }}>
            <Ionicons name="arrow-back" size={22} color="#FFFFFF" />
          </Pressable>
          <Brand size={44} />
          <Text style={{ color: "#FFFFFF", ...type.display, fontSize: 26, marginTop: space.xxl, maxWidth: 260 }}>
            Precisou? Alguém faz.
          </Text>
          <Text style={{ color: "rgba(255,255,255,0.72)", ...type.body, marginTop: space.sm }}>
            Entre para pedir ajuda ou encontrar trabalhos em Parauapebas.
          </Text>
        </View>

        <View style={{ paddingHorizontal: space.xl, marginTop: -space.xxl, gap: space.md }}>
          {formFields}
        </View>

        <View style={{ flex: 1, minHeight: space.xxl }} />

        <View style={{ paddingHorizontal: space.xl, paddingBottom: Math.max(insets.bottom, space.xl) }}>
          {demoBlock}
        </View>
      </ScrollView>
    </View>
  );
}
