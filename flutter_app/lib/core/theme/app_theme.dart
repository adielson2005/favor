import 'app_colors.dart';
import 'app_typography.dart';

/// Bundles colors + type for the current mode — the single object screens
/// pull everything visual from, same idea as the RN app's `useTheme()`
/// returning `{ colors }` (frontend/src/theme.tsx), extended with typography
/// since Flutter has no font-family-per-weight files to reach for separately.
class AppTheme {
  final AppColors colors;
  final AppTypography type;
  final bool isDark;

  AppTheme({required this.colors, required this.isDark}) : type = AppTypography(colors.ink);

  static final light = AppTheme(colors: AppColors.light, isDark: false);
  static final dark = AppTheme(colors: AppColors.dark, isDark: true);
}
