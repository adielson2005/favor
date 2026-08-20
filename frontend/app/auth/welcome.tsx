import { useRouter } from "expo-router";
import React from "react";
import { Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Animated, { FadeIn, FadeInDown } from "react-native-reanimated";

import { Btn } from "@/src/components/ui";
import { Brand } from "@/src/components/Logo";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useBreakpoint } from "@/src/hooks/use-breakpoint";
import { radius, space, type, useTheme } from "@/src/theme";

export default function Welcome() {
  const { colors } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { isDesktop } = useBreakpoint();

  const legal = (
    <Animated.View entering={FadeIn.duration(400).delay(240)} style={{ paddingHorizontal: space.xl, alignItems: "center", gap: space.xs }}>
      <Text style={{ color: colors.faint, ...type.micro, textAlign: "center" }}>
        Ao continuar, você concorda com os{" "}
        <Text style={{ color: colors.muted, fontFamily: fonts.bodySemiBold }}>Termos de Uso</Text>
        {" "}e a{" "}
        <Text style={{ color: colors.muted, fontFamily: fonts.bodySemiBold }}>Política de Privacidade</Text>.
      </Text>
    </Animated.View>
  );

  if (isDesktop) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", padding: space.xxxl }}>
        <View style={{ width: "100%", maxWidth: 420, backgroundColor: colors.surface, borderRadius: radius.xl, borderWidth: 1, borderColor: colors.border, padding: space.xxxl, gap: space.xxxl, alignItems: "center" }}>
          <Animated.View entering={FadeIn.duration(400)} style={{ alignItems: "center", gap: space.lg }}>
            <Brand size={44} />
            <Text style={{ color: colors.muted, ...type.body, textAlign: "center", maxWidth: 280 }}>
              Precisou? <Text style={{ color: colors.primary, fontFamily: fonts.bodyBold }}>FAZUM</Text> pedido.
            </Text>
          </Animated.View>
          <Animated.View entering={FadeInDown.duration(400).delay(120)} style={{ gap: space.md, width: "100%" }}>
            <Btn testID="welcome-login-button" title="Entrar" onPress={() => router.push("/auth/login")} />
            <Btn testID="welcome-signup-button" title="Criar conta" variant="secondary" onPress={() => router.push("/auth/signup")} />
          </Animated.View>
          {legal}
        </View>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top, paddingBottom: Math.max(insets.bottom, space.xl) }}>
      <View style={{ flex: 1, justifyContent: "center", paddingHorizontal: space.xl, gap: space.xxxl }}>
        <Animated.View entering={FadeIn.duration(400)} style={{ alignItems: "center", gap: space.lg }}>
          <Brand size={52} />
          <Text style={{ color: colors.muted, ...type.body, textAlign: "center", maxWidth: 280 }}>
            Precisou? <Text style={{ color: colors.primary, fontFamily: fonts.bodyBold }}>FAZUM</Text> pedido.
          </Text>
        </Animated.View>

        <Animated.View entering={FadeInDown.duration(400).delay(120)} style={{ gap: space.md, width: "100%", maxWidth: 420, alignSelf: "center" }}>
          <Btn testID="welcome-login-button" title="Entrar" onPress={() => router.push("/auth/login")} />
          <Btn testID="welcome-signup-button" title="Criar conta" variant="secondary" onPress={() => router.push("/auth/signup")} />
        </Animated.View>
      </View>

      {legal}
    </View>
  );
}
