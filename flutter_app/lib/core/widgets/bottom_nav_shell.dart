import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../theme/app_theme.dart';
import '../theme/theme_controller.dart';

class _NavItem {
  final String path;
  final IconData icon;
  final IconData activeIcon;
  final String label;
  const _NavItem(this.path, this.icon, this.activeIcon, this.label);
}

const _navItems = [
  _NavItem('/', Icons.home_outlined, Icons.home_rounded, 'Home'),
  _NavItem('/create', Icons.add_circle_outline, Icons.add_circle_rounded, 'Pedir'),
  _NavItem('/wallet', Icons.account_balance_wallet_outlined, Icons.account_balance_wallet_rounded, 'Carteira'),
  _NavItem('/profile', Icons.person_outline_rounded, Icons.account_circle_rounded, 'Perfil'),
];

/// Breakpoint above which we switch from the mobile bottom tab bar to the
/// desktop top nav — matches the width where the single-column mobile
/// layouts elsewhere in the app would otherwise look stretched/empty.
const _desktopBreakpoint = 840.0;

/// Persistent navigation, wrapped around every authenticated route via a
/// ShellRoute in app_router.dart — visible everywhere in the logged-in app,
/// including detail screens (order, chat, etc.), not just the 4 tab roots.
/// Renders as a bottom tab bar on mobile widths, a top text nav on desktop
/// widths (same 4 destinations either way).
class BottomNavShell extends ConsumerWidget {
  final Widget child;
  const BottomNavShell({super.key, required this.child});

  static int _currentIndex(String location) {
    // Longest non-root path match wins, so e.g. '/wallet/withdraw' still
    // highlights "Carteira" — '/' only matches the exact root.
    var bestIndex = 0;
    var bestLength = -1;
    for (var i = 0; i < _navItems.length; i++) {
      final path = _navItems[i].path;
      final matches = path == '/' ? location == '/' : location.startsWith(path);
      if (matches && path.length > bestLength) {
        bestIndex = i;
        bestLength = path.length;
      }
    }
    return bestIndex;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = ref.watch(themeProviderForScreens);
    final colors = theme.colors;
    final location = GoRouterState.of(context).matchedLocation;
    final currentIndex = _currentIndex(location);
    final isDesktop = MediaQuery.sizeOf(context).width >= _desktopBreakpoint;
    void onSelect(int i) => context.go(_navItems[i].path);

    if (isDesktop) {
      return Scaffold(
        backgroundColor: colors.bg,
        body: Column(
          children: [
            _DesktopTopNav(theme: theme, currentIndex: currentIndex, onSelect: onSelect),
            Expanded(child: child),
          ],
        ),
      );
    }

    return Scaffold(
      backgroundColor: colors.bg,
      body: child,
      bottomNavigationBar: _MobileBottomNav(theme: theme, currentIndex: currentIndex, onSelect: onSelect),
    );
  }
}

/// Top nav for wide screens — OLX-style: brand mark on the left, plain text
/// destinations (no icons), current one picked out with color + underline.
class _DesktopTopNav extends StatelessWidget {
  final AppTheme theme;
  final int currentIndex;
  final ValueChanged<int> onSelect;

  const _DesktopTopNav({required this.theme, required this.currentIndex, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    return Container(
      decoration: BoxDecoration(color: colors.surface, border: Border(bottom: BorderSide(color: colors.border))),
      child: SafeArea(
        bottom: false,
        child: SizedBox(
          height: 64,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32),
            child: Row(
              children: [
                Text('fazum', style: theme.type.h2.copyWith(color: colors.primary)),
                const SizedBox(width: 48),
                for (var i = 0; i < _navItems.length; i++) ...[
                  if (i != 0) const SizedBox(width: 32),
                  _DesktopNavLink(
                    theme: theme,
                    label: _navItems[i].label,
                    selected: i == currentIndex,
                    onTap: () => onSelect(i),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _DesktopNavLink extends StatelessWidget {
  final AppTheme theme;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _DesktopNavLink({required this.theme, required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    final color = selected ? colors.primary : colors.muted;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(6),
      hoverColor: colors.primarySoft.withValues(alpha: 0.4),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(label, style: theme.type.body.copyWith(color: color, fontWeight: selected ? FontWeight.w700 : FontWeight.w500)),
            const SizedBox(height: 6),
            AnimatedContainer(
              duration: const Duration(milliseconds: 150),
              height: 2,
              width: 22,
              color: selected ? colors.primary : Colors.transparent,
            ),
          ],
        ),
      ),
    );
  }
}

/// Bottom tab bar for mobile widths — the active tab gets a soft rounded
/// pill behind the icon (not just a color swap), rounded icon glyphs, and a
/// touch of elevation so it reads as a real app chrome piece, not a plain row.
class _MobileBottomNav extends StatelessWidget {
  final AppTheme theme;
  final int currentIndex;
  final ValueChanged<int> onSelect;

  const _MobileBottomNav({required this.theme, required this.currentIndex, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    return SafeArea(
      top: false,
      child: Container(
        margin: const EdgeInsets.fromLTRB(12, 0, 12, 10),
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 8),
        decoration: BoxDecoration(
          color: colors.surface,
          borderRadius: BorderRadius.circular(22),
          border: Border.all(color: colors.border),
          boxShadow: [BoxShadow(color: colors.scrim, blurRadius: 16, offset: const Offset(0, 6))],
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            for (var i = 0; i < _navItems.length; i++)
              _MobileNavButton(
                theme: theme,
                item: _navItems[i],
                selected: i == currentIndex,
                onTap: () => onSelect(i),
              ),
          ],
        ),
      ),
    );
  }
}

class _MobileNavButton extends StatelessWidget {
  final AppTheme theme;
  final _NavItem item;
  final bool selected;
  final VoidCallback onTap;

  const _MobileNavButton({required this.theme, required this.item, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    final color = selected ? colors.primary : colors.faint;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        curve: Curves.easeOut,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? colors.primarySoft : Colors.transparent,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(selected ? item.activeIcon : item.icon, color: color, size: 22),
            if (selected) ...[
              const SizedBox(width: 6),
              Text(item.label, style: theme.type.micro.copyWith(color: color, letterSpacing: 0)),
            ],
          ],
        ),
      ),
    );
  }
}
