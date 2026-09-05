import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../theme/app_theme.dart';
import '../theme/theme_controller.dart';

/// Reads the current [AppTheme] the same way RN screens call `useTheme()` —
/// `AppScope.of(context).theme` inside any widget under [AppScope].
class AppScope extends ConsumerWidget {
  final Widget Function(BuildContext context, AppTheme theme) builder;
  const AppScope({super.key, required this.builder});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final themeState = ref.watch(themeControllerProvider);
    return builder(context, themeState.theme);
  }
}
