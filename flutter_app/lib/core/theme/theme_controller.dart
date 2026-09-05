import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app_theme.dart';

/// light | dark | system — same three-state preference as the RN app's
/// ThemePref (frontend/src/theme.tsx), persisted under the same key
/// ("faze:theme") so the choice reads the same conceptually across clients,
/// even though each stores it in its own local storage.
enum ThemePref { light, dark, system }

const _themePrefKey = 'faze:theme';

class ThemeState {
  final ThemePref pref;
  final Brightness systemBrightness;
  const ThemeState({required this.pref, required this.systemBrightness});

  bool get isDark => switch (pref) {
        ThemePref.dark => true,
        ThemePref.light => false,
        ThemePref.system => systemBrightness == Brightness.dark,
      };

  AppTheme get theme => isDark ? AppTheme.dark : AppTheme.light;
}

class ThemeController extends StateNotifier<ThemeState> {
  ThemeController()
      : super(const ThemeState(pref: ThemePref.system, systemBrightness: Brightness.light)) {
    _hydrate();
  }

  Future<void> _hydrate() async {
    final prefs = await SharedPreferences.getInstance();
    final stored = prefs.getString(_themePrefKey);
    final pref = ThemePref.values.firstWhere(
      (p) => p.name == stored,
      orElse: () => ThemePref.system,
    );
    state = ThemeState(pref: pref, systemBrightness: state.systemBrightness);
  }

  Future<void> setPref(ThemePref pref) async {
    state = ThemeState(pref: pref, systemBrightness: state.systemBrightness);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_themePrefKey, pref.name);
  }

  /// Called from a MediaQuery-observing widget when the OS brightness
  /// changes, so `ThemePref.system` stays live without a restart.
  void reportSystemBrightness(Brightness brightness) {
    if (state.systemBrightness != brightness) {
      state = ThemeState(pref: state.pref, systemBrightness: brightness);
    }
  }
}

final themeControllerProvider = StateNotifierProvider<ThemeController, ThemeState>(
  (ref) => ThemeController(),
);

/// Convenience read-only view for screens that only need the resolved
/// [AppTheme] (colors + type), not the raw preference/system-brightness
/// state — most screens, mirroring how RN components just call `useTheme()`
/// and destructure `{ colors }`.
final themeProviderForScreens = Provider<AppTheme>((ref) => ref.watch(themeControllerProvider).theme);
