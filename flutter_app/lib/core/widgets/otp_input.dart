import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../theme/app_theme.dart';

/// 6-digit code entry — functional equivalent of
/// frontend/src/components/OtpInput.tsx (single controller, auto-fires
/// onComplete once 6 digits are present, red border on `error`). One text
/// field with letter-spacing rather than 6 separate boxes — same behavior,
/// simpler to keep in sync with Flutter's IME on Android/iOS.
class OtpInput extends StatelessWidget {
  final TextEditingController controller;
  final AppTheme theme;
  final bool error;
  final ValueChanged<String> onChanged;
  final ValueChanged<String> onComplete;

  const OtpInput({
    super.key,
    required this.controller,
    required this.theme,
    required this.onChanged,
    required this.onComplete,
    this.error = false,
  });

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    return SizedBox(
      width: 220,
      child: TextField(
        controller: controller,
        autofocus: true,
        textAlign: TextAlign.center,
        keyboardType: TextInputType.number,
        inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(6)],
        style: theme.type.h1.copyWith(letterSpacing: 12),
        decoration: InputDecoration(
          counterText: '',
          filled: true,
          fillColor: colors.surface,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: BorderSide(color: error ? colors.danger : colors.border, width: 1.5),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: BorderSide(color: error ? colors.danger : colors.border, width: 1.5),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: BorderSide(color: error ? colors.danger : colors.primary, width: 1.5),
          ),
        ),
        onChanged: (value) {
          onChanged(value);
          if (value.length == 6) onComplete(value);
        },
      ),
    );
  }
}
