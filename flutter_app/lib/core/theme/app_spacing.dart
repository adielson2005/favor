/// Same scale as frontend/src/theme.tsx's `space` export — reuse these instead
/// of ad hoc numbers, same rule that applies on the RN side.
class AppSpacing {
  const AppSpacing._();
  static const xs = 4.0;
  static const sm = 8.0;
  static const md = 12.0;
  static const lg = 16.0;
  static const xl = 20.0;
  static const xxl = 24.0;
  static const xxxl = 32.0;
}

/// Same scale as frontend/src/theme.tsx's `radius` export.
class AppRadius {
  const AppRadius._();
  static const sm = 12.0;
  static const md = 16.0;
  static const lg = 20.0;
  static const xl = 24.0;
  static const pill = 999.0;
}
