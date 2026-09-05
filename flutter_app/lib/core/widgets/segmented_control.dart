import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Mirrors frontend/src/components/ui.tsx's `Segmented` — the "Preciso de
/// ajuda" / "Quero fazer" mode toggle on Home.
class SegmentedOption {
  final String key;
  final String label;
  const SegmentedOption(this.key, this.label);
}

class SegmentedControl extends StatelessWidget {
  final List<SegmentedOption> options;
  final String value;
  final ValueChanged<String> onChanged;
  final AppTheme theme;

  const SegmentedControl({
    super.key,
    required this.options,
    required this.value,
    required this.onChanged,
    required this.theme,
  });

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(color: colors.alt, borderRadius: BorderRadius.circular(14)),
      child: Row(
        children: options.map((opt) {
          final active = opt.key == value;
          return Expanded(
            child: GestureDetector(
              onTap: () => onChanged(opt.key),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 150),
                padding: const EdgeInsets.symmetric(vertical: 10),
                decoration: BoxDecoration(
                  color: active ? colors.surface : Colors.transparent,
                  borderRadius: BorderRadius.circular(10),
                  boxShadow: active
                      ? [BoxShadow(color: colors.scrim, blurRadius: 4, offset: const Offset(0, 1))]
                      : null,
                ),
                alignment: Alignment.center,
                child: Text(
                  opt.label,
                  style: theme.type.small.copyWith(
                    color: active ? colors.ink : colors.muted,
                    fontWeight: active ? FontWeight.bold : FontWeight.w500,
                  ),
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }
}
