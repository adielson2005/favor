import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import 'app_button.dart';

/// Mirrors frontend/src/components/ui.tsx's `EmptyState` — icon, title,
/// optional body copy, optional action button.
class EmptyState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? body;
  final String? actionTitle;
  final VoidCallback? onAction;
  final AppTheme theme;

  const EmptyState({
    super.key,
    required this.icon,
    required this.title,
    required this.theme,
    this.body,
    this.actionTitle,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 32, horizontal: 20),
      child: Column(
        children: [
          Icon(icon, size: 40, color: colors.faint),
          const SizedBox(height: 12),
          Text(title, style: theme.type.bodyStrong.copyWith(color: colors.ink), textAlign: TextAlign.center),
          if (body != null) ...[
            const SizedBox(height: 6),
            Text(body!, style: theme.type.small.copyWith(color: colors.muted), textAlign: TextAlign.center),
          ],
          if (actionTitle != null && onAction != null) ...[
            const SizedBox(height: 16),
            AppButton(title: actionTitle!, theme: theme, variant: AppButtonVariant.secondary, onPressed: onAction),
          ],
        ],
      ),
    );
  }
}
