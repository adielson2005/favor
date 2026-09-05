import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Mirrors frontend/src/components/ui.tsx's `Skeleton` — a pulsing
/// placeholder block shown while data loads, not a static grey box.
class AppSkeleton extends StatefulWidget {
  final double height;
  final double radius;
  final AppTheme theme;

  const AppSkeleton({super.key, required this.theme, this.height = 64, this.radius = 14});

  @override
  State<AppSkeleton> createState() => _AppSkeletonState();
}

class _AppSkeletonState extends State<AppSkeleton> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: const Duration(milliseconds: 900))
      ..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colors = widget.theme.colors;
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        return Container(
          height: widget.height,
          decoration: BoxDecoration(
            color: Color.lerp(colors.alt, colors.surface, _controller.value),
            borderRadius: BorderRadius.circular(widget.radius),
          ),
        );
      },
    );
  }
}
