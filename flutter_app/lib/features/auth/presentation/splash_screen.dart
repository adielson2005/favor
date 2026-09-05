import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/theme_controller.dart';

/// Shown only while AuthController is still hydrating (reading the stored
/// token, validating it against /auth/me). No RN equivalent file exists
/// (the RN app just doesn't render a route decision until `ready`), but a
/// real screen here avoids a blank frame on native cold start.
class SplashScreen extends ConsumerWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = ref.watch(themeProviderForScreens);
    return Scaffold(
      backgroundColor: theme.colors.primary,
      body: Center(
        child: Text('fazum', style: theme.type.display.copyWith(color: theme.colors.onPrimary)),
      ),
    );
  }
}
