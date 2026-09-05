import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/router/app_router.dart';
import 'core/theme/theme_controller.dart';

void main() {
  runApp(const ProviderScope(child: FazumApp()));
}

/// Root widget. Session bootstrap (reading the stored token, unblocking
/// ApiClient's request queue, validating against /auth/me) now lives entirely
/// in AuthController (features/auth/application/auth_controller.dart) — FASE 4
/// moved it there from this file so there is exactly one place that owns
/// session state, not two racing against each other.
class FazumApp extends ConsumerWidget {
  const FazumApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final themeState = ref.watch(themeControllerProvider);
    final brightness = MediaQuery.platformBrightnessOf(context);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(themeControllerProvider.notifier).reportSystemBrightness(brightness);
    });

    final theme = themeState.theme;
    final router = ref.watch(appRouterProvider);

    return MaterialApp.router(
      title: 'fazum',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: theme.isDark ? Brightness.dark : Brightness.light,
        scaffoldBackgroundColor: theme.colors.bg,
        colorScheme: theme.isDark
            ? ColorScheme.dark(primary: theme.colors.primary, surface: theme.colors.surface)
            : ColorScheme.light(primary: theme.colors.primary, surface: theme.colors.surface),
      ),
      routerConfig: router,
    );
  }
}
