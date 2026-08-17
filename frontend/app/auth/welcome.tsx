import { useRouter } from "expo-router";
import React from "react";
import { Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Animated, { FadeIn, FadeInDown } from "react-native-reanimated";

import { Btn } from "@/src/components/ui";
import { Brand } from "@/src/components/Logo";
import { fonts } from "@/src/hooks/use-app-fonts";
import { space, type, useTheme } from "@/src/theme";

export default function Welcome() {
  const { colors } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();

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

      <Animated.View entering={FadeIn.duration(400).delay(240)} style={{ paddingHorizontal: space.xl, alignItems: "center", gap: space.xs }}>
        <Text style={{ color: colors.faint, ...type.micro, textAlign: "center" }}>
          Ao continuar, você concorda com os{" "}
          <Text style={{ color: colors.muted, fontFamily: fonts.bodySemiBold }}>Termos de Uso</Text>
          {" "}e a{" "}
          <Text style={{ color: colors.muted, fontFamily: fonts.bodySemiBold }}>Política de Privacidade</Text>.
        </Text>
      </Animated.View>
    </View>
  );
}
