import '../../../core/models/user.dart';
import '../../../core/networking/api_client.dart';

/// Result of any call that issues/refreshes a session (register, login,
/// Google auth) — same {token, user} shape backend/routes/auth.py returns
/// from all three, mirrored from frontend/src/auth.tsx's `applySession`.
class AuthResult {
  final String token;
  final AppUser user;
  /// Present only when SMTP/SMS aren't configured server-side (dev fallback)
  /// — backend/routes/auth.py returns the OTP directly instead of sending it.
  final String? devCodeEmail;
  final String? devCodePhone;

  const AuthResult({required this.token, required this.user, this.devCodeEmail, this.devCodePhone});

  factory AuthResult.fromJson(Map<String, dynamic> json) => AuthResult(
        token: json['token'] as String,
        user: AppUser.fromJson(json['user'] as Map<String, dynamic>),
        devCodeEmail: json['dev_code_email'] as String?,
        devCodePhone: json['dev_code_phone'] as String?,
      );
}

/// Mirrors frontend/src/auth.tsx's API calls 1:1 against backend/routes/auth.py.
/// Pure data layer — no token persistence, no app state. AuthController owns
/// deciding what to do with the result (same split as the RN app: auth.tsx's
/// AuthProvider calls storage.secureSet itself around these same endpoints).
class AuthRepository {
  AuthRepository(this._client);
  final ApiClient _client;

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
    final json = await _client.post<Map<String, dynamic>>('/auth/register', body: {
      'name': name,
      'email': email,
      'phone': phone,
      'password': password,
      'city_id': cityId,
      'neighborhood_id': neighborhoodId,
      'preference': preference,
      'accept_terms': acceptTerms,
    });
    return AuthResult.fromJson(json);
  }

  Future<AuthResult> login({required String identifier, required String password}) async {
    final json = await _client.post<Map<String, dynamic>>('/auth/login', body: {
      'identifier': identifier.trim(),
      'password': password,
    });
    return AuthResult.fromJson(json);
  }

  Future<AuthResult> loginWithGoogle({required String idToken, String? nonce, String? cityId}) async {
    final json = await _client.post<Map<String, dynamic>>('/auth/google', body: {
      'id_token': idToken,
      'nonce': nonce,
      'city_id': cityId ?? 'city-parauapebas',
    });
    return AuthResult.fromJson(json);
  }

  Future<AppUser> me() async {
    final json = await _client.get<Map<String, dynamic>>('/auth/me');
    return AppUser.fromJson(json);
  }

  Future<Map<String, dynamic>> forgotPassword(String email) =>
      _client.post<Map<String, dynamic>>('/auth/forgot-password', body: {'email': email});

  Future<void> resetPassword({required String email, required String code, required String password}) =>
      _client.post<Map<String, dynamic>>('/auth/reset-password', body: {
        'email': email,
        'code': code,
        'password': password,
      });

  Future<Map<String, dynamic>> sendVerification() =>
      _client.post<Map<String, dynamic>>('/auth/send-verification');

  Future<AppUser> verifyEmail(String code) async {
    final json = await _client.post<Map<String, dynamic>>('/auth/verify-email', body: {'code': code});
    return AppUser.fromJson(json);
  }

  Future<Map<String, dynamic>> sendPhoneVerification() =>
      _client.post<Map<String, dynamic>>('/auth/send-phone-verification');

  Future<AppUser> verifyPhone(String code) async {
    final json = await _client.post<Map<String, dynamic>>('/auth/verify-phone', body: {'code': code});
    return AppUser.fromJson(json);
  }

  Future<void> changePassword({String? currentPassword, required String newPassword}) =>
      _client.post<Map<String, dynamic>>('/auth/change-password', body: {
        'current_password': currentPassword,
        'new_password': newPassword,
      });

  Future<void> deleteAccount() => _client.delete<Map<String, dynamic>>('/auth/me');

  /// change-email/change-phone bump token_version server-side (the point is to
  /// invalidate any session an attacker could have kept after taking over the
  /// old contact channel) — which also invalidates the CALLER's own current
  /// token, so both endpoints hand back a fresh one in the same response
  /// (backend/routes/auth.py) instead of forcing a re-login mid-flow.
  Future<ChangeContactResult> changeEmail({required String email, required String password}) async {
    final json = await _client.post<Map<String, dynamic>>('/auth/change-email', body: {
      'email': email,
      'password': password,
    });
    return ChangeContactResult.fromJson(json);
  }

  Future<ChangeContactResult> changePhone({required String phone, String? password}) async {
    final json = await _client.post<Map<String, dynamic>>('/auth/change-phone', body: {
      'phone': phone,
      'password': password,
    });
    return ChangeContactResult.fromJson(json);
  }
}

class ChangeContactResult {
  final String token;
  final AppUser user;
  final String? devCode;

  const ChangeContactResult({required this.token, required this.user, this.devCode});

  factory ChangeContactResult.fromJson(Map<String, dynamic> json) => ChangeContactResult(
        token: json['token'] as String,
        user: AppUser.fromJson(json['user'] as Map<String, dynamic>),
        devCode: json['dev_code'] as String?,
      );
}
