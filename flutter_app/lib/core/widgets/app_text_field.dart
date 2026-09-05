import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Mirrors frontend/src/components/ui.tsx's `Field` — label above, error
/// text below, border color reacts to focus/error the same way.
class AppTextField extends StatelessWidget {
  final String? label;
  final String? error;
  final TextEditingController controller;
  final AppTheme theme;
  final bool obscureText;
  final TextInputType? keyboardType;
  final String? placeholder;
  final String? testID;
  final ValueChanged<String>? onChanged;

  const AppTextField({
    super.key,
    required this.controller,
    required this.theme,
    this.label,
    this.error,
    this.obscureText = false,
    this.keyboardType,
    this.placeholder,
    this.testID,
    this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (label != null) ...[
          Text(label!.toUpperCase(), style: theme.type.micro.copyWith(color: colors.muted)),
          const SizedBox(height: 6),
        ],
        TextField(
          key: testID != null ? Key(testID!) : null,
          controller: controller,
          obscureText: obscureText,
          keyboardType: keyboardType,
          onChanged: onChanged,
          style: theme.type.body,
          decoration: InputDecoration(
            hintText: placeholder,
            hintStyle: theme.type.body.copyWith(color: colors.faint),
            filled: true,
            fillColor: colors.surface,
            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(14),
              borderSide: BorderSide(color: colors.border, width: 1.5),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(14),
              borderSide: BorderSide(color: error != null ? colors.danger : colors.border, width: 1.5),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(14),
              borderSide: BorderSide(color: error != null ? colors.danger : colors.primary, width: 1.5),
            ),
          ),
        ),
        if (error != null) ...[
          const SizedBox(height: 4),
          Text(error!, style: theme.type.small.copyWith(color: colors.danger)),
        ],
      ],
    );
  }
}
