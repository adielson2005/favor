import 'dart:math';

import 'package:google_sign_in/google_sign_in.dart';

import '../config/app_environment.dart';

/// Result the backend's POST /auth/google expects — see
/// AuthRepository.loginWithGoogle and routes/auth.py's _verify_google_id_token.
class GoogleAuthResult {
  final String idToken;
  final String nonce;
  const GoogleAuthResult({required this.idToken, required this.nonce});
}

class GoogleAuthException implements Exception {
  final String message;
  final bool cancelled;
  const GoogleAuthException(this.message, {this.cancelled = false});

  factory GoogleAuthException.cancelled() =>
      const GoogleAuthException('Login com Google cancelado.', cancelled: true);

  @override
  String toString() => message;
}

/// Thin wrapper around google_sign_in v7's event/init-based API, reduced to
/// the one thing routes/auth.py's /auth/google needs: a fresh ID token plus
/// the nonce it was requested with (checked server-side for replay
/// protection — see models.py's GoogleAuthIn.nonce).
///
/// GOOGLE_SERVER_CLIENT_ID must be the same Web-application OAuth client ID
/// as the backend's GOOGLE_CLIENT_ID — google_sign_in_android's README is
/// explicit that Android needs this passed as `serverClientId` when there's
/// no google-services.json (there isn't one in this project), and the
/// backend verifies the ID token's audience against that exact client ID.
class GoogleAuthService {
  GoogleAuthService._();
  static final GoogleAuthService instance = GoogleAuthService._();

  bool _initialized = false;
  String? _nonce;

  bool get isConfigured => AppEnvironment.googleServerClientId.isNotEmpty;

  String _generateNonce() {
    final rand = Random.secure();
    return List.generate(16, (_) => rand.nextInt(256).toRadixString(16).padLeft(2, '0')).join();
  }

  Future<void> _ensureInitialized() async {
    if (_initialized) return;
    _nonce = _generateNonce();
    await GoogleSignIn.instance.initialize(
      serverClientId: AppEnvironment.googleServerClientId,
      nonce: _nonce,
    );
    _initialized = true;
  }

  /// Triggers the interactive Google sign-in UI and returns a fresh ID token.
  /// Throws [GoogleAuthException] (with `cancelled: true` if the user simply
  /// backed out) rather than letting the raw plugin exception leak into UI code.
  Future<GoogleAuthResult> signIn() async {
    if (!isConfigured) {
      throw const GoogleAuthException(
        'Login com Google não está configurado neste app. Defina GOOGLE_SERVER_CLIENT_ID no build.',
      );
    }
    await _ensureInitialized();
    try {
      final account = await GoogleSignIn.instance.authenticate();
      final idToken = account.authentication.idToken;
      if (idToken == null) {
        throw const GoogleAuthException('O Google não devolveu um token válido. Tente novamente.');
      }
      return GoogleAuthResult(idToken: idToken, nonce: _nonce!);
    } on GoogleSignInException catch (e) {
      if (e.code == GoogleSignInExceptionCode.canceled) {
        throw GoogleAuthException.cancelled();
      }
      throw GoogleAuthException('Não foi possível entrar com o Google: ${e.description ?? e.code}');
    }
  }
}
