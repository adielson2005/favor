import '../../../core/models/user.dart';

/// Mirrors frontend/src/auth.tsx's AuthState shape: `ready` gates routing
/// decisions (splash vs. login vs. home) until boot-time hydration finishes,
/// same as the RN app never rendering a route decision before `ready` flips.
class AuthState {
  final bool ready;
  final String? token;
  final AppUser? user;

  const AuthState({required this.ready, this.token, this.user});

  const AuthState.initial() : ready = false, token = null, user = null;

  bool get isAuthenticated => token != null && user != null;

  AuthState copyWith({bool? ready, String? token, AppUser? user, bool clearSession = false}) {
    if (clearSession) {
      return AuthState(ready: ready ?? this.ready, token: null, user: null);
    }
    return AuthState(
      ready: ready ?? this.ready,
      token: token ?? this.token,
      user: user ?? this.user,
    );
  }
}
