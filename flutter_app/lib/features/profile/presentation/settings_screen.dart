import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/theme_controller.dart';

const _prefLabels = {
  ThemePref.light: 'Claro',
  ThemePref.dark: 'Escuro',
  ThemePref.system: 'Automático (sistema)',
};

const _prefIcons = {
  ThemePref.light: Icons.light_mode_outlined,
  ThemePref.dark: Icons.dark_mode_outlined,
  ThemePref.system: Icons.brightness_auto_outlined,
};

/// The one thing this app had built (ThemeController, light/dark/system,
/// persisted under "faze:theme") but never exposed any UI to change — see
/// theme_controller.dart. Profile screen's gear icon used to be a dead stub.
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = ref.watch(themeProviderForScreens);
    final colors = theme.colors;
    final currentPref = ref.watch(themeControllerProvider).pref;

    return Scaffold(
      backgroundColor: colors.bg,
      body: SafeArea(
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Row(children: [
              IconButton(onPressed: () => context.pop(), icon: Icon(Icons.arrow_back, color: colors.ink)),
              Expanded(child: Text('Configurações', style: theme.type.h2.copyWith(fontSize: 17))),
            ]),
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                Text('TEMA', style: theme.type.micro.copyWith(color: colors.muted)),
                const SizedBox(height: 8),
                Container(
                  decoration: BoxDecoration(
                    color: colors.surface,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: colors.border),
                  ),
                  child: Column(
                    children: ThemePref.values.map((pref) {
                      final selected = pref == currentPref;
                      return InkWell(
                        onTap: () => ref.read(themeControllerProvider.notifier).setPref(pref),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                          child: Row(children: [
                            Icon(_prefIcons[pref], size: 20, color: selected ? colors.primary : colors.muted),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(_prefLabels[pref]!,
                                  style: theme.type.body.copyWith(
                                    color: selected ? colors.ink : colors.muted,
                                    fontWeight: selected ? FontWeight.bold : FontWeight.w500,
                                  )),
                            ),
                            if (selected) Icon(Icons.check, size: 18, color: colors.primary),
                          ]),
                        ),
                      );
                    }).toList(),
                  ),
                ),
              ],
            ),
          ),
        ]),
      ),
    );
  }
}
