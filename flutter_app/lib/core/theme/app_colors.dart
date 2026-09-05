import 'package:flutter/widgets.dart';

/// Same palette as the React Native app's frontend/src/theme.tsx, ported value
/// for value — not reinterpreted. Both clients hit the same backend and should
/// look like the same product, not two different brands.
///
/// Light runs true white (surface == bg; cards separate by border/shadow
/// alone). Dark deliberately avoids the navy-black-plus-neon-accent look that
/// reads as generic "AI product" dark mode — warm charcoal instead of navy,
/// slightly less electric green/lime. See the RN file's own comment for the
/// full rationale; kept here only as a pointer, not duplicated at length.
class AppColors {
  final Color bg, surface, alt, ink, muted, faint;
  final Color primary, onPrimary, primarySoft;
  final Color green, greenSoft, danger, dangerSoft, amber, border, scrim;
  final Color accent, onAccent, accentSoft;

  const AppColors({
    required this.bg,
    required this.surface,
    required this.alt,
    required this.ink,
    required this.muted,
    required this.faint,
    required this.primary,
    required this.onPrimary,
    required this.primarySoft,
    required this.green,
    required this.greenSoft,
    required this.danger,
    required this.dangerSoft,
    required this.amber,
    required this.border,
    required this.scrim,
    required this.accent,
    required this.onAccent,
    required this.accentSoft,
  });

  static const light = AppColors(
    bg: Color(0xFFFFFFFF), surface: Color(0xFFFFFFFF), alt: Color(0xFFF3F1EC),
    ink: Color(0xFF0E1A2B), muted: Color(0xFF5C6670), faint: Color(0xFF646E76),
    primary: Color(0xFF12864A), onPrimary: Color(0xFFFFFFFF), primarySoft: Color(0xFFE1F5E9),
    green: Color(0xFF1E8E5A), greenSoft: Color(0xFFE2F2E9),
    danger: Color(0xFFC2453B), dangerSoft: Color(0xFFF9E9E7),
    amber: Color(0xFFB07B18), border: Color(0xFFE2DED4), scrim: Color(0x730D1323),
    accent: Color(0xFFA4ED0E), onAccent: Color(0xFF0E1A2B), accentSoft: Color(0xFFEEFAD1),
  );

  static const dark = AppColors(
    bg: Color(0xFF181614), surface: Color(0xFF221F1B), alt: Color(0xFF2B2823),
    ink: Color(0xFFF2EFE9), muted: Color(0xFFADA79B), faint: Color(0xFF8F897C),
    primary: Color(0xFF2FAE68), onPrimary: Color(0xFF07160D), primarySoft: Color(0xFF1B3324),
    green: Color(0xFF57BE86), greenSoft: Color(0xFF1F2C24),
    danger: Color(0xFFD9756C), dangerSoft: Color(0xFF332420),
    amber: Color(0xFFD9AC5A), border: Color(0xFF332E27), scrim: Color(0x990A0806),
    accent: Color(0xFFB9E23E), onAccent: Color(0xFF161310), accentSoft: Color(0xFF262C16),
  );
}
