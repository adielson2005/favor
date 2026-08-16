import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useRef, useState } from "react";
import { Dimensions, Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Btn } from "@/src/components/ui";
import { useTheme } from "@/src/theme";
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
  const [page, setPage] = useState(0);
  const scrollRef = useRef<ScrollView>(null);
  const width = Dimensions.get("window").width;

  const finish = async () => {
    await storage.setItem("faze:onboarded", true);
    router.replace("/(tabs)/home");
  };

  const next = () => {
    if (page < SLIDES.length - 1) scrollRef.current?.scrollTo({ x: (page + 1) * width, animated: true });
    else finish();
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + 12, paddingBottom: Math.max(insets.bottom, 16) }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingHorizontal: 24 }}>
        <Text style={{ fontSize: 22, fontWeight: "800", color: colors.primary, letterSpacing: -1 }}>FAZÊ</Text>
        <Pressable onPress={finish} hitSlop={10} testID="onboarding-skip"><Text style={{ color: colors.muted, fontWeight: "600", fontSize: 14 }}>Pular</Text></Pressable>
      </View>
      <ScrollView
        ref={scrollRef}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onMomentumScrollEnd={(e) => setPage(Math.round(e.nativeEvent.contentOffset.x / width))}
      >
        {SLIDES.map((slide) => (
          <View key={slide.title} style={{ width, alignItems: "center", justifyContent: "center", paddingHorizontal: 40, gap: 18 }}>
            <View style={{ width: 96, height: 96, borderRadius: 48, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" }}>
              <Ionicons name={slide.icon} size={40} color={colors.primary} />
            </View>
            <Text style={{ color: colors.ink, fontSize: 26, fontWeight: "800", textAlign: "center", letterSpacing: -0.5 }}>{slide.title}</Text>
            <Text style={{ color: colors.muted, fontSize: 15, textAlign: "center", lineHeight: 23 }}>{slide.body}</Text>
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
    </View>
  );
}
