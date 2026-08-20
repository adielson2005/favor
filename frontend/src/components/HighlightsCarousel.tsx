import { Ionicons } from "@expo/vector-icons";
import React, { useRef, useState } from "react";
import { Image, ImageSourcePropType, LayoutChangeEvent, Pressable, ScrollView, View } from "react-native";

import { useBreakpoint } from "@/src/hooks/use-breakpoint";
import { radius, space, useTheme } from "@/src/theme";

// Source banners are exported at this aspect ratio — new highlights should match
// it (or get letterboxed/cover-cropped) so the carousel never jumps in height.
const BANNER_ASPECT_RATIO = 1672 / 941;

// Either a static banner image, or a rendered node (e.g. a code-built promo card
// like FazumPayBanner) for highlights that aren't a designed asset.
export type Highlight = { id: string; image?: ImageSourcePropType; content?: React.ReactNode; onPress?: () => void };

// Horizontal "destaques/anúncios/atualizações" strip for the top of Home. Two
// paging systems, one per input method: touch devices swipe (native ScrollView
// paging + dot indicators — nothing to click, nothing extra to render); desktop
// has no swipe gesture, so it gets hoverable prev/next arrow buttons instead.
// Both drive the same scrollRef, so dots stay in sync either way.
export function HighlightsCarousel({ items, testID }: { items: Highlight[]; testID?: string }) {
  const { colors } = useTheme();
  const { isDesktop } = useBreakpoint();
  const [width, setWidth] = useState(0);
  const [page, setPage] = useState(0);
  const scrollRef = useRef<ScrollView>(null);

  const onLayout = (e: LayoutChangeEvent) => {
    const w = e.nativeEvent.layout.width;
    if (w && w !== width) setWidth(w);
  };

  const goTo = (next: number) => {
    const clamped = Math.max(0, Math.min(items.length - 1, next));
    scrollRef.current?.scrollTo({ x: clamped * width, animated: true });
    setPage(clamped);
  };

  if (!items.length) return null;

  return (
    <View testID={testID} onLayout={onLayout} style={{ position: "relative" }}>
      {width > 0 && (
        <>
          <ScrollView
            ref={scrollRef}
            horizontal
            pagingEnabled
            showsHorizontalScrollIndicator={false}
            decelerationRate="fast"
            onMomentumScrollEnd={(e) => setPage(Math.round(e.nativeEvent.contentOffset.x / width))}
          >
            {items.map((item) => (
              <Pressable
                key={item.id}
                testID={testID ? `${testID}-item` : undefined}
                disabled={!item.onPress}
                onPress={item.onPress}
                style={{ width, height: width / BANNER_ASPECT_RATIO }}
              >
                {item.content ?? <Image source={item.image} style={{ width: "100%", height: "100%", borderRadius: radius.lg }} resizeMode="cover" />}
              </Pressable>
            ))}
          </ScrollView>

          {isDesktop && items.length > 1 && (
            <>
              {page > 0 && (
                <Pressable
                  testID={testID ? `${testID}-prev` : undefined}
                  onPress={() => goTo(page - 1)}
                  style={{ position: "absolute", left: 8, top: "50%", marginTop: -18, width: 36, height: 36, borderRadius: 18, backgroundColor: "rgba(0,0,0,0.35)", alignItems: "center", justifyContent: "center" }}
                >
                  <Ionicons name="chevron-back" size={18} color="#FFFFFF" />
                </Pressable>
              )}
              {page < items.length - 1 && (
                <Pressable
                  testID={testID ? `${testID}-next` : undefined}
                  onPress={() => goTo(page + 1)}
                  style={{ position: "absolute", right: 8, top: "50%", marginTop: -18, width: 36, height: 36, borderRadius: 18, backgroundColor: "rgba(0,0,0,0.35)", alignItems: "center", justifyContent: "center" }}
                >
                  <Ionicons name="chevron-forward" size={18} color="#FFFFFF" />
                </Pressable>
              )}
            </>
          )}

          {items.length > 1 && (
            <View style={{ flexDirection: "row", justifyContent: "center", gap: 6, marginTop: space.sm }}>
              {items.map((_, i) => (
                <Pressable key={i} disabled={!isDesktop} onPress={() => goTo(i)} hitSlop={6}>
                  <View style={{ width: i === page ? 16 : 6, height: 6, borderRadius: 3, backgroundColor: i === page ? colors.primary : colors.border }} />
                </Pressable>
              ))}
            </View>
          )}
        </>
      )}
    </View>
  );
}
