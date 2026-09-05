import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/errors/api_exception.dart';
import '../../../core/models/user.dart';
import '../../../core/networking/api_client.dart';
import '../../../core/providers.dart';
import '../../../core/storage/secure_storage.dart';
import '../data/auth_repository.dart';
import 'auth_state.dart';

final authRepositoryProvider = Provider<AuthRepository>(
  (ref) => AuthRepository(ref.watch(apiClientProvider)),
);

/// Session state machine — mirrors frontend/src/auth.tsx's AuthProvider
/// exactly: on boot, read the stored token, unblock ApiClient's request
/// queue (`markAuthReady`) BEFORE calling /auth/me (that call itself waits
/// on the same gate), and drop the token if it turns out to be stale/revoked
/// (e.g. token_version bumped server-side since it was issued).
class AuthController extends StateNotifier<AuthState> {
  AuthController(this._repository, this._apiClient) : super(const AuthState.initial()) {
    _bootstrap();
  }

  final AuthRepository _repository;
  final ApiClient _apiClient;

  Future<void> _bootstrap() async {
    final stored = await SecureStorage.instance.readUserToken();
    if (stored != null) _apiClient.setToken(stored);
    _apiClient.markAuthReady();

    if (stored == null) {
      state = state.copyWith(ready: true);
      return;
    }
    try {
      final user = await _repository.me();
      state = AuthState(ready: true, token: stored, user: user);
    } on ApiException {
      await SecureStorage.instance.clearUserToken();
      _apiClient.setToken(null);
      state = const AuthState(ready: true);
    }
  }

  Future<void> _applySession(AuthResult result) => _syncSession(result.token, result.user);

  /// Shared by login/register/loginWithGoogle (via [_applySession]) AND by
  /// change-email/change-phone, which also issue a fresh token as a side
  /// effect of bumping token_version — see AuthRepository.changeEmail's doc.
  Future<void> _syncSession(String token, AppUser user) async {
    await SecureStorage.instance.writeUserToken(token);
    _apiClient.setToken(token);
    state = AuthState(ready: true, token: token, user: user);
  }

  Future<AuthResult> login({required String identifier, required String password}) async {
    final result = await _repository.login(identifier: identifier, password: password);
    await _applySession(result);
    return result;
  }

  Future<AuthResult> register({
    required String name,
    required String email,
    required String phone,
    required String password,
    required String cityId,
    String? neighborhoodId,
    String preference = 'both',
    required bool acceptTerms,
  }) async {
    final result = await _repository.register(
      name: name,
      email: email,
      phone: phone,
      password: password,
      cityId: cityId,
      neighborhoodId: neighborhoodId,
      preference: preference,
      acceptTerms: acceptTerms,
    );
    await _applySession(result);
    return result;
  }

  Future<AuthResult> loginWithGoogle({required String idToken, String? nonce, String? cityId}) async {
    final result = await _repository.loginWithGoogle(idToken: idToken, nonce: nonce, cityId: cityId);
    await _applySession(result);
    return result;
  }

  Future<void> refreshUser() async {
    try {
      final user = await _repository.me();
      state = state.copyWith(user: user);
    } on ApiException {
      // Keep last known user — same "swallow and keep stale" behavior as
      // frontend/src/auth.tsx's refreshUser.
    }
  }

  Future<ChangeContactResult> changeEmail({required String email, required String password}) async {
    final result = await _repository.changeEmail(email: email, password: password);
    await _syncSession(result.token, result.user);
    return result;
  }

  Future<ChangeContactResult> changePhone({required String phone, String? password}) async {
    final result = await _repository.changePhone(phone: phone, password: password);
    await _syncSession(result.token, result.user);
    return result;
  }

  Future<void> logout() async {
    await SecureStorage.instance.clearUserToken();
    _apiClient.setToken(null);
    state = state.copyWith(clearSession: true);
  }

  Future<void> deleteAccount() async {
    await _repository.deleteAccount();
    await logout();
  }
}

final authControllerProvider = StateNotifierProvider<AuthController, AuthState>(
  (ref) => AuthController(ref.watch(authRepositoryProvider), ref.watch(apiClientProvider)),
);
