import { Ionicons } from "@expo/vector-icons";
import * as ImageManipulator from "expo-image-manipulator";
import React, { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Alert, Image, PanResponder, Text, useWindowDimensions, View } from "react-native";

import { Btn, Sheet } from "@/src/components/ui";
import { space, useTheme } from "@/src/theme";

const MIN_ZOOM = 1;
const MAX_ZOOM = 3;
const OUTPUT_SIZE = 480;

// Drag-to-reposition + slider-to-zoom avatar cropper. Built on PanResponder (core
// React Native, no extra native module) so the exact same code path works on web
// (mouse drag) and native (touch drag) — react-native-gesture-handler is installed
// but never wired up (no GestureHandlerRootView at the app root), so leaning on it
// here would mean bootstrapping that just for this.
//
// PanResponder.create(...) is captured once via useRef and never recreated, so its
// callbacks close over whatever naturalW/naturalH/containerSize/disabled were on the
// very FIRST render — before the picked image has finished loading. Every value those
// callbacks need is therefore mirrored into a ref that's updated on every render, and
// the callbacks read `.current` instead of the render-scoped variable directly.
export function AvatarCropModal({ visible, uri, onCancel, onConfirm }: {
  visible: boolean; uri: string | null; onCancel: () => void; onConfirm: (base64: string) => void;
}) {
  const { colors } = useTheme();
  const { width: winW } = useWindowDimensions();
  const containerSize = Math.min(300, winW - 96);

  const [naturalW, setNaturalW] = useState(0);
  const [naturalH, setNaturalH] = useState(0);
  const [scale, setScale] = useState(1);
  const [translate, setTranslate] = useState({ x: 0, y: 0 });
  const [processing, setProcessing] = useState(false);

  const naturalWRef = useRef(0);
  const naturalHRef = useRef(0);
  const containerSizeRef = useRef(containerSize);
  const scaleRef = useRef(1);
  const translateRef = useRef({ x: 0, y: 0 });
  const dragStartRef = useRef({ x: 0, y: 0 });
  naturalWRef.current = naturalW;
  naturalHRef.current = naturalH;
  containerSizeRef.current = containerSize;

  useEffect(() => {
    if (!visible || !uri) return;
    setNaturalW(0); setNaturalH(0); setScale(1); setTranslate({ x: 0, y: 0 });
    scaleRef.current = 1; translateRef.current = { x: 0, y: 0 };
    Image.getSize(uri, (w, h) => { setNaturalW(w); setNaturalH(h); }, () => {
      Alert.alert("Não foi possível abrir a imagem", "Tente escolher outra foto.");
      onCancel();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, uri]);

  const baseScale = naturalW && naturalH ? Math.max(containerSize / naturalW, containerSize / naturalH) : 1;
  const displayedW = naturalW * baseScale * scale;
  const displayedH = naturalH * baseScale * scale;
  const left = (containerSize - displayedW) / 2 + translate.x;
  const top = (containerSize - displayedH) / 2 + translate.y;

  // Reads exclusively from refs so it behaves correctly even when called from the
  // frozen PanResponder closure created on the first (pre-image-load) render.
  const clampTranslate = (x: number, y: number, s: number) => {
    const nW = naturalWRef.current, nH = naturalHRef.current, cSize = containerSizeRef.current;
    const bScale = nW && nH ? Math.max(cSize / nW, cSize / nH) : 1;
    const dW = nW * bScale * s;
    const dH = nH * bScale * s;
    const maxX = Math.max(0, (dW - cSize) / 2);
    const maxY = Math.max(0, (dH - cSize) / 2);
    return { x: Math.min(maxX, Math.max(-maxX, x)), y: Math.min(maxY, Math.max(-maxY, y)) };
  };

  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dx) > 2 || Math.abs(g.dy) > 2,
      onPanResponderGrant: () => { dragStartRef.current = translateRef.current; },
      onPanResponderMove: (_, gesture) => {
        const next = clampTranslate(dragStartRef.current.x + gesture.dx, dragStartRef.current.y + gesture.dy, scaleRef.current);
        translateRef.current = next;
        setTranslate(next);
      },
    })
  ).current;

  const handleZoomChange = (z: number) => {
    const next = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z));
    setScale(next);
    scaleRef.current = next;
    const clamped = clampTranslate(translateRef.current.x, translateRef.current.y, next);
    translateRef.current = clamped;
    setTranslate(clamped);
  };

  const handleConfirm = async () => {
    if (!uri || !naturalW || !naturalH || !displayedW || !displayedH) return;
    setProcessing(true);
    try {
      const factor = naturalW / displayedW;
      const cropSize = containerSize * factor;
      let originX = -((containerSize - displayedW) / 2 + translate.x) * factor;
      let originY = -((containerSize - displayedH) / 2 + translate.y) * factor;
      originX = Math.max(0, Math.min(naturalW - cropSize, originX));
      originY = Math.max(0, Math.min(naturalH - cropSize, originY));
      const result = await ImageManipulator.manipulateAsync(
        uri,
        [{ crop: { originX, originY, width: cropSize, height: cropSize } }, { resize: { width: OUTPUT_SIZE, height: OUTPUT_SIZE } }],
        { compress: 0.75, format: ImageManipulator.SaveFormat.JPEG, base64: true }
      );
      if (!result.base64) throw new Error("no base64");
      onConfirm(`data:image/jpeg;base64,${result.base64}`);
    } catch {
      Alert.alert("Não foi possível ajustar a foto", "Tente novamente.");
    } finally {
      setProcessing(false);
    }
  };

  const ready = naturalW > 0 && naturalH > 0;

  return (
    <Sheet visible={visible} onClose={onCancel} title="Ajustar foto" scroll={false}>
      <View style={{ alignItems: "center", paddingVertical: space.md, paddingBottom: 24, gap: space.lg }}>
        <View
          style={{
            width: containerSize, height: containerSize, borderRadius: containerSize / 2,
            overflow: "hidden", backgroundColor: colors.alt, borderWidth: 2, borderColor: colors.primary,
          }}
          {...panResponder.panHandlers}
        >
          {ready && uri ? (
            <Image source={{ uri }} style={{ position: "absolute", width: displayedW, height: displayedH, left, top }} />
          ) : (
            <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
              <ActivityIndicator color={colors.primary} />
            </View>
          )}
        </View>

        <Text style={{ color: colors.faint, fontSize: 12 }}>Arraste para reposicionar</Text>

        <View style={{ flexDirection: "row", alignItems: "center", gap: space.md, width: containerSize }}>
          <Ionicons name="image-outline" size={16} color={colors.faint} />
          <ZoomSlider value={scale} min={MIN_ZOOM} max={MAX_ZOOM} onChange={handleZoomChange} disabled={!ready} />
          <Ionicons name="image" size={22} color={colors.faint} />
        </View>

        <View style={{ flexDirection: "row", gap: space.sm, width: "100%", marginTop: space.sm }}>
          <View style={{ flex: 1 }}><Btn title="Cancelar" variant="secondary" onPress={onCancel} disabled={processing} testID="avatar-crop-cancel" /></View>
          <View style={{ flex: 1 }}><Btn title="Usar foto" onPress={handleConfirm} loading={processing} disabled={!ready} testID="avatar-crop-confirm" /></View>
        </View>
      </View>
    </Sheet>
  );
}

function ZoomSlider({ value, min, max, onChange, disabled }: { value: number; min: number; max: number; onChange: (v: number) => void; disabled?: boolean }) {
  const { colors } = useTheme();
  const trackWidth = 160;
  const thumbSize = 20;
  const usableWidth = trackWidth - thumbSize;

  const valueToX = (v: number) => ((v - min) / (max - min)) * usableWidth;
  const xToValue = (x: number) => min + (Math.max(0, Math.min(usableWidth, x)) / usableWidth) * (max - min);

  const valueRef = useRef(value);
  const disabledRef = useRef(disabled);
  const onChangeRef = useRef(onChange);
  valueRef.current = value;
  disabledRef.current = disabled;
  onChangeRef.current = onChange;

  const startXRef = useRef(0);
  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => !disabledRef.current,
      onMoveShouldSetPanResponder: () => !disabledRef.current,
      onPanResponderGrant: () => { startXRef.current = valueToX(valueRef.current); },
      onPanResponderMove: (_, gesture) => {
        const nextX = Math.max(0, Math.min(usableWidth, startXRef.current + gesture.dx));
        onChangeRef.current(xToValue(nextX));
      },
    })
  ).current;

  const thumbX = valueToX(value);

  return (
    <View style={{ flex: 1, height: thumbSize, justifyContent: "center", opacity: disabled ? 0.4 : 1 }} {...panResponder.panHandlers}>
      <View style={{ height: 4, borderRadius: 2, backgroundColor: colors.border }} />
      <View style={{ position: "absolute", left: 0, height: 4, borderRadius: 2, backgroundColor: colors.primary, width: thumbX + thumbSize / 2 }} />
      <View style={{ position: "absolute", left: thumbX, top: 0, width: thumbSize, height: thumbSize, borderRadius: thumbSize / 2, backgroundColor: colors.primary, borderWidth: 2, borderColor: colors.bg }} />
    </View>
  );
}
