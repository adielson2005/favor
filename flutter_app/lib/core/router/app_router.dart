import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/auth/application/auth_controller.dart';
import '../../features/auth/presentation/forgot_password_screen.dart';
import '../../features/auth/presentation/login_screen.dart';
import '../../features/auth/presentation/signup_screen.dart';
import '../../features/auth/presentation/splash_screen.dart';
import '../../features/auth/presentation/verify_contact_screen.dart';
import '../../features/auth/presentation/welcome_screen.dart';
import '../../features/chat/presentation/chat_screen.dart';
import '../../features/home/presentation/home_screen.dart';
import '../../features/notifications/presentation/notifications_screen.dart';
import '../../features/orders/presentation/order_detail_screen.dart';
import '../../features/profile/presentation/profile_screen.dart';
import '../../features/profile/presentation/public_profile_screen.dart';
import '../../features/profile/presentation/security_screen.dart';
import '../../features/services/presentation/create_order_screen.dart';
import '../../features/wallet/presentation/bank_accounts_screen.dart';
import '../../features/wallet/presentation/wallet_screen.dart';
import '../../features/wallet/presentation/withdraw_screen.dart';

/// Routes only a signed-out visitor should see — an authenticated user
/// landing on one of these (e.g. after a hot-restart with a valid session)
/// bounces to home. verify-email/verify-phone are deliberately NOT in this
/// set: those are reached by an already-authenticated user (e.g. right after
/// register()), same as frontend/app/auth/verify-email.tsx assumes a logged
/// in `user` from context rather than being a pre-auth entry point.
const _guestOnlyRoutes = {'/auth/welcome', '/auth/login', '/auth/signup', '/auth/forgot-password'};

/// Redirect rules mirror what the RN app enforces implicitly via each
/// screen's own `useRequireAuth()` hook + index.tsx's completeness check:
///   - not ready yet                        → splash
///   - ready, no session, non-auth route    → bounce to /auth/welcome
///   - ready, has session, guest-only route → bounce to home
final appRouterProvider = Provider<GoRouter>((ref) {
  // Eagerly creates AuthController (and its boot-time hydration) as soon as
  // the router itself is built, rather than waiting for the first widget
  // that happens to watch it.
  ref.watch(authControllerProvider.notifier);

  return GoRouter(
    initialLocation: '/',
    refreshListenable: _AuthListenable(ref),
    redirect: (context, state) {
      final auth = ref.read(authControllerProvider);
      final isGuestOnlyRoute = _guestOnlyRoutes.contains(state.matchedLocation);
      final isAuthRoute = state.matchedLocation.startsWith('/auth');

      if (!auth.ready) return null; // let the / route render SplashScreen
      if (!auth.isAuthenticated && !isAuthRoute) return '/auth/welcome';
      if (auth.isAuthenticated && isGuestOnlyRoute) return '/';
      return null;
    },
    routes: [
      GoRoute(path: '/', builder: (context, state) => const _RootRoute()),
      GoRoute(path: '/create', builder: (context, state) => const CreateOrderScreen()),
      GoRoute(
        path: '/order/:id',
        builder: (context, state) => OrderDetailScreen(orderId: state.pathParameters['id']!),
      ),
      GoRoute(
        path: '/chat/:id',
        builder: (context, state) => ChatScreen(orderId: state.pathParameters['id']!),
      ),
      GoRoute(path: '/notifications', builder: (context, state) => const NotificationsScreen()),
      GoRoute(path: '/profile', builder: (context, state) => const ProfileScreen()),
      GoRoute(path: '/security', builder: (context, state) => const SecurityScreen()),
      GoRoute(
        path: '/user/:id',
        builder: (context, state) => PublicProfileScreen(userId: state.pathParameters['id']!),
      ),
      GoRoute(path: '/wallet', builder: (context, state) => const WalletScreen()),
      GoRoute(path: '/wallet/bank-accounts', builder: (context, state) => const BankAccountsScreen()),
      GoRoute(path: '/wallet/withdraw', builder: (context, state) => const WithdrawScreen()),
      GoRoute(path: '/auth/welcome', builder: (context, state) => const WelcomeScreen()),
      GoRoute(path: '/auth/login', builder: (context, state) => const LoginScreen()),
      GoRoute(path: '/auth/signup', builder: (context, state) => const SignupScreen()),
      GoRoute(path: '/auth/forgot-password', builder: (context, state) => const ForgotPasswordScreen()),
      GoRoute(
        path: '/auth/verify-email',
        builder: (context, state) => const VerifyContactScreen(channel: ContactChannel.email),
      ),
      GoRoute(
        path: '/auth/verify-phone',
        builder: (context, state) => const VerifyContactScreen(channel: ContactChannel.phone),
      ),
    ],
  );
});

/// Bridges Riverpod's authControllerProvider into go_router's
/// Listenable-based refresh mechanism, so a login/logout immediately
/// re-evaluates `redirect` instead of waiting for the next navigation.
class _AuthListenable extends ChangeNotifier {
  _AuthListenable(Ref ref) {
    ref.listen(authControllerProvider, (previous, next) => notifyListeners());
  }
}

/// Root route: SplashScreen while auth is still hydrating, real HomeScreen
/// once authenticated (FASE 5). The redirect above already guarantees an
/// unauthenticated, ready session never reaches this widget.
class _RootRoute extends ConsumerWidget {
  const _RootRoute();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authControllerProvider);
    if (!auth.ready) return const SplashScreen();
    return const HomeScreen();
  }
}
