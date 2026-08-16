import { Ionicons } from "@expo/vector-icons";
import React from "react";
import { Text, View } from "react-native";

import { Btn } from "@/src/components/ui";
import { dark, light } from "@/src/theme";

// Class component is required here — React only calls getDerivedStateFromError/
// componentDidCatch on class components, there is no hook equivalent. This is the
// one place in the app allowed to catch a render crash instead of letting it blank
// the whole screen; every other component should let errors surface normally.
type Props = { children: React.ReactNode };
type State = { hasError: boolean };

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    console.warn("[ErrorBoundary] caught a render error:", error);
  }

  reset = () => this.setState({ hasError: false });

  render() {
    if (!this.state.hasError) return this.props.children;
    // No ThemeProvider access this deep (it may itself be what crashed) — pick by
    // OS/browser color scheme directly rather than depending on app context.
    const colors = typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches ? dark : light;
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", padding: 32, gap: 16 }}>
        <View style={{ width: 64, height: 64, borderRadius: 32, backgroundColor: colors.dangerSoft, alignItems: "center", justifyContent: "center" }}>
          <Ionicons name="alert-circle-outline" size={28} color={colors.danger} />
        </View>
        <Text style={{ color: colors.ink, fontSize: 17, fontWeight: "700", textAlign: "center" }}>Algo deu errado.</Text>
        <Text style={{ color: colors.muted, fontSize: 14, textAlign: "center", lineHeight: 20 }}>Não conseguimos mostrar essa tela agora. Tente novamente.</Text>
        <Btn title="Tentar novamente" onPress={this.reset} />
      </View>
    );
  }
}
