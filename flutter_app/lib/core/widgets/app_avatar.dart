import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Mirrors frontend/src/components/ui.tsx's `Avatar` — initials on a
/// primary-soft circle when there's no avatar image.
class AppAvatar extends StatelessWidget {
  final String initials;
  final double size;
  final AppTheme theme;
  final String? imageBase64;

  const AppAvatar({
    super.key,
    required this.initials,
    required this.theme,
    this.size = 42,
    this.imageBase64,
  });

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(color: colors.primarySoft, shape: BoxShape.circle),
      alignment: Alignment.center,
      child: Text(
        initials,
        style: theme.type.bodyStrong.copyWith(color: colors.primary, fontSize: size * 0.36),
      ),
    );
  }
}
