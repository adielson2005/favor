// Proves FASE 14 (Testes) coverage of real, previously-untested AuthRepository
// methods: changePassword, forgotPassword/resetPassword, and the
// send-verification resend endpoints. All reachable from real UI already
// (profile_screen.dart's password sheet, forgot_password_screen.dart,
// verify_contact_screen.dart's resend button) but never exercised by a test
// before this.
//
//   flutter test test/auth_extra_live_test.dart --dart-define=API_BASE_URL=http://localhost:8000
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';

import 'package:fazum/core/errors/api_exception.dart';
import 'package:fazum/core/networking/api_client.dart';
import 'package:fazum/features/auth/data/auth_repository.dart';

String _randomPhone() {
  final rand = Random();
  final digits = List.generate(8, (_) => rand.nextInt(10)).join();
  return '949$digits';
}

void main() {
  ApiClient.instance.markAuthReady();

  test('changePassword requires the correct current password and invalidates the old session token', () async {
    final api = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;
    final auth = AuthRepository(api);
    final reg = await auth.register(
      name: 'Muda Senha $tag',
      email: 'muda_senha_$tag@example.com',
      phone: _randomPhone(),
      password: 'SenhaOriginal!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'client',
      acceptTerms: true,
    );
    api.setToken(reg.token);

    expect(
      () => auth.changePassword(currentPassword: 'senha-errada', newPassword: 'SenhaNova!45'),
      throwsA(isA<ApiException>()),
    );

    await auth.changePassword(currentPassword: 'SenhaOriginal!23', newPassword: 'SenhaNova!45');

    // token_version was bumped server-side — the token this same client is
    // still holding must now be rejected.
    expect(() => auth.me(), throwsA(isA<ApiException>()));

    final relogin = await auth.login(identifier: 'muda_senha_$tag@example.com', password: 'SenhaNova!45');
    expect(relogin.user.id, reg.user.id);
  });

  test('forgotPassword + resetPassword issues a working new password and invalidates old sessions', () async {
    final api = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;
    final auth = AuthRepository(api);
    final email = 'esqueci_$tag@example.com';
    final reg = await auth.register(
      name: 'Esqueci Senha $tag',
      email: email,
      phone: _randomPhone(),
      password: 'SenhaAntiga!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'client',
      acceptTerms: true,
    );
    api.setToken(reg.token);

    final forgot = await auth.forgotPassword(email);
    expect(forgot['dev_code'], isNotNull);

    await auth.resetPassword(email: email, code: forgot['dev_code'] as String, password: 'SenhaRecuperada!45');

    api.setToken(reg.token);
    expect(() => auth.me(), throwsA(isA<ApiException>()));

    final relogin = await auth.login(identifier: email, password: 'SenhaRecuperada!45');
    expect(relogin.user.id, reg.user.id);
  });

  test('sendVerification/sendPhoneVerification resend a real code, then report already-verified', () async {
    final api = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;
    final auth = AuthRepository(api);
    final reg = await auth.register(
      name: 'Reenviar Codigo $tag',
      email: 'reenviar_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase14!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'client',
      acceptTerms: true,
    );
    api.setToken(reg.token);

    final resendEmail = await auth.sendVerification();
    expect(resendEmail['dev_code'], isNotNull);
    await auth.verifyEmail(resendEmail['dev_code'] as String);
    final alreadyEmail = await auth.sendVerification();
    expect(alreadyEmail['dev_code'], isNull);
    expect(alreadyEmail['message'], contains('já está verificado'));

    final resendPhone = await auth.sendPhoneVerification();
    expect(resendPhone['dev_code'], isNotNull);
    await auth.verifyPhone(resendPhone['dev_code'] as String);
    final alreadyPhone = await auth.sendPhoneVerification();
    expect(alreadyPhone['dev_code'], isNull);
    expect(alreadyPhone['message'], contains('já está verificado'));
  });
}
