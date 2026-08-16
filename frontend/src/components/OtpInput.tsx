import React, { useRef, useState } from "react";
import { Pressable, TextInput, View, Text } from "react-native";
import Animated, { useAnimatedStyle, useSharedValue, withSequence, withTiming } from "react-native-reanimated";

import { fonts } from "@/src/hooks/use-app-fonts";
import { useTheme } from "@/src/theme";

// One real (invisible) TextInput drives the whole thing — native keyboard, paste,
// and backspace all just work, and we render `length` boxes reading off its value.
// Splitting into per-digit TextInputs+refs is the usual approach but it reinvents
// cursor/paste/backspace handling that the platform already does correctly.
export function OtpInput({ length = 6, value, onChange, onComplete, error, autoFocus }: {
  length?: number; value: string; onChange: (v: string) => void; onComplete?: (v: string) => void; error?: boolean; autoFocus?: boolean;
}) {
  const { colors } = useTheme();
  const inputRef = useRef<TextInput>(null);
  const [focused, setFocused] = useState(false);
  const shake = useSharedValue(0);

  React.useEffect(() => {
    if (error) shake.value = withSequence(withTiming(-6, { duration: 40 }), withTiming(6, { duration: 40 }), withTiming(-4, { duration: 40 }), withTiming(0, { duration: 40 }));
  }, [error, shake]);

  const shakeStyle = useAnimatedStyle(() => ({ transform: [{ translateX: shake.value }] }));

  const handleChange = (text: string) => {
    const digits = text.replace(/[^0-9]/g, "").slice(0, length);
    onChange(digits);
    if (digits.length === length) onComplete?.(digits);
  };

  return (
    <Pressable testID="otp-input" onPress={() => inputRef.current?.focus()}>
      <Animated.View style={[{ flexDirection: "row", gap: 8, justifyContent: "center" }, shakeStyle]}>
        {Array.from({ length }).map((_, i) => {
          const char = value[i];
          const isCursor = focused && i === value.length;
          return (
            <View key={i} style={{
              width: 44, height: 52, borderRadius: 12, alignItems: "center", justifyContent: "center",
              borderWidth: isCursor ? 2 : 1.5,
              borderColor: error ? colors.danger : isCursor ? colors.primary : colors.border,
              backgroundColor: colors.surface,
            }}>
              <Text style={{ fontFamily: fonts.headingExtraBold, fontSize: 20, color: colors.ink }}>{char || ""}</Text>
            </View>
          );
        })}
      </Animated.View>
      <TextInput
        ref={inputRef}
        testID="otp-hidden-input"
        value={value}
        onChangeText={handleChange}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        keyboardType="number-pad"
        textContentType="oneTimeCode"
        autoComplete="sms-otp"
        maxLength={length}
        autoFocus={autoFocus}
        style={{ position: "absolute", opacity: 0, width: 1, height: 1 }}
      />
    </Pressable>
  );
}
