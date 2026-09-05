import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

enum AppButtonVariant { primary, secondary, ghost, danger }

/// Mirrors frontend/src/components/ui.tsx's `Btn` — same variants, same
/// disabled/loading affordance, so behavior reads identically to the RN app.
class AppButton extends StatelessWidget {
  final String title;
  final VoidCallback? onPressed;
  final AppButtonVariant variant;
  final bool loading;
  final AppTheme theme;

  const AppButton({
    super.key,
    required this.title,
    required this.theme,
    this.onPressed,
    this.variant = AppButtonVariant.primary,
    this.loading = false,
  });

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    final disabled = onPressed == null || loading;

    final (bg, fg) = switch (variant) {
      AppButtonVariant.primary => (colors.primary, colors.onPrimary),
      AppButtonVariant.secondary => (colors.alt, colors.ink),
      AppButtonVariant.ghost => (Colors.transparent, colors.muted),
      AppButtonVariant.danger => (colors.dangerSoft, colors.danger),
    };

    return Opacity(
      opacity: disabled && !loading ? 0.5 : 1,
      child: SizedBox(
        height: 52,
        child: ElevatedButton(
          onPressed: disabled ? null : onPressed,
          style: ElevatedButton.styleFrom(
            backgroundColor: bg,
            foregroundColor: fg,
            disabledBackgroundColor: bg,
            disabledForegroundColor: fg,
            elevation: 0,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          ),
          child: loading
              ? SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2.4, color: fg),
                )
              : Text(title, style: theme.type.bodyStrong.copyWith(color: fg)),
        ),
      ),
    );
  }
}
