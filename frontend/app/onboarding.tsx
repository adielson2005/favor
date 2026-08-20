import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useRef, useState } from "react";
import { Pressable, ScrollView, Text, useWindowDimensions, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Brand } from "@/src/components/Logo";
import { Btn } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useBreakpoint } from "@/src/hooks/use-breakpoint";
import { radius, space, useTheme } from "@/src/theme";
import { storage } from "@/src/utils/storage";

const SLIDES = [
  { icon: "hand-left-outline" as const, title: "Precisa de ajuda?", body: "Encontre alguém para realizar pequenas tarefas em Parauapebas." },
  { icon: "cash-outline" as const, title: "Quer ganhar dinheiro?", body: "Encontre trabalhos e serviços perto de você." },
  { icon: "checkmark-circle-outline" as const, title: "Tudo pronto.", body: "Publique ou encontre seu primeiro serviço." },
];

export default function Onboarding() {
  const { colors } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { isDesktop } = useBreakpoint();
  const [page, setPage] = useState(0);
  const scrollRef = useRef<ScrollView>(null);
  const { width: windowWidth } = useWindowDimensions();
  // On desktop the carousel no longer stretches edge to edge — each "page" is
  // capped to a compact card width instead of the full (often huge) window width.
  const slideWidth = isDesktop ? Math.min(480, windowWidth) : windowWidth;

  const finish = async () => {
    await storage.setItem("faze:onboarded", true);
    router.replace("/(tabs)/home");
  };

  const next = () => {
    if (page < SLIDES.length - 1) scrollRef.current?.scrollTo({ x: (page + 1) * slideWidth, animated: true });
    else finish();
  };

  const content = (
    <>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingHorizontal: 24 }}>
        <Brand size={30} />
        <Pressable onPress={finish} hitSlop={10} testID="onboarding-skip"><Text style={{ color: colors.muted, fontFamily: fonts.bodySemiBold, fontSize: 14 }}>Pular</Text></Pressable>
      </View>
      <ScrollView
        ref={scrollRef}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        style={isDesktop ? { width: slideWidth, alignSelf: "center" } : undefined}
        onMomentumScrollEnd={(e) => setPage(Math.round(e.nativeEvent.contentOffset.x / slideWidth))}
      >
        {SLIDES.map((slide) => (
          <View key={slide.title} style={{ width: slideWidth, alignItems: "center", justifyContent: "center", paddingHorizontal: 40, gap: 18 }}>
            <View style={{ width: 96, height: 96, borderRadius: 48, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" }}>
              <Ionicons name={slide.icon} size={40} color={colors.primary} />
            </View>
            <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 26, textAlign: "center", letterSpacing: -0.5 }}>{slide.title}</Text>
            <Text style={{ color: colors.muted, fontFamily: fonts.body, fontSize: 15, textAlign: "center", lineHeight: 23 }}>{slide.body}</Text>
          </View>
        ))}
      </ScrollView>
      <View style={{ flexDirection: "row", justifyContent: "center", gap: 6, marginBottom: 24 }}>
        {SLIDES.map((_, i) => (
          <View key={i} style={{ width: i === page ? 20 : 7, height: 7, borderRadius: 4, backgroundColor: i === page ? colors.primary : colors.border }} />
        ))}
      </View>
      <View style={{ paddingHorizontal: 24 }}>
        <Btn testID="onboarding-next" title={page === SLIDES.length - 1 ? "Começar" : "Continuar"} onPress={next} icon="arrow-forward" />
      </View>
    </>
  );

  if (isDesktop) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", padding: space.xxxl }}>
        <View style={{ width: "100%", maxWidth: 560, paddingVertical: 32, backgroundColor: colors.surface, borderRadius: radius.xl, borderWidth: 1, borderColor: colors.border, gap: 12 }}>
          {content}
        </View>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + 12, paddingBottom: Math.max(insets.bottom, 16) }}>
      {content}
    </View>
  );
}
