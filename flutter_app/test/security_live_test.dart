// Proves FASE 13 (Segurança) end-to-end against the REAL backend — same
// standard as profile_live_test.dart. change-email/change-phone are tested
// at the repository layer (not through AuthController) since the backend
// contract — password reauth, verification reset, and a fresh session token
// handed back in the same response — is what needs proving; AuthController
// only adds local session-storage plumbing on top of it.
//
//   flutter test test/security_live_test.dart --dart-define=API_BASE_URL=http://localhost:8000
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';

import 'package:fazum/core/errors/api_exception.dart';
import 'package:fazum/core/networking/api_client.dart';
import 'package:fazum/core/repositories/blocks_repository.dart';
import 'package:fazum/core/repositories/chat_repository.dart';
import 'package:fazum/features/auth/data/auth_repository.dart';

String _randomPhone() {
  final rand = Random();
  final digits = List.generate(8, (_) => rand.nextInt(10)).join();
  return '949$digits';
}

void main() {
  ApiClient.instance.markAuthReady();

  test('change-email requires the correct password, resets verification, and issues a working new token', () async {
    final api = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;
    final auth = AuthRepository(api);
    final reg = await auth.register(
      name: 'Seguranca Email $tag',
      email: 'seg_email_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase13!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'client',
      acceptTerms: true,
    );
    api.setToken(reg.token);
    await auth.verifyEmail(reg.devCodeEmail!);

    expect(
      () => auth.changeEmail(email: 'novo_$tag@example.com', password: 'senha-errada'),
      throwsA(isA<ApiException>()),
    );

    final newEmail = 'novo_$tag@example.com';
    final result = await auth.changeEmail(email: newEmail, password: 'TesteFase13!23');
    expect(result.user.verifiedEmail, isFalse);
    expect(result.devCode, isNotNull);

    api.setToken(result.token);
    final me = await auth.me();
    expect(me.id, reg.user.id);
    expect(me.verifiedEmail, isFalse);
  });

  test('change-phone requires the correct password, resets verification, and issues a working new token', () async {
    final api = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;
    final auth = AuthRepository(api);
    final reg = await auth.register(
      name: 'Seguranca Telefone $tag',
      email: 'seg_tel_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase13!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'client',
      acceptTerms: true,
    );
    api.setToken(reg.token);
    await auth.verifyPhone(reg.devCodePhone!);

    final newPhone = _randomPhone();
    expect(
      () => auth.changePhone(phone: newPhone, password: 'senha-errada'),
      throwsA(isA<ApiException>()),
    );

    final result = await auth.changePhone(phone: newPhone, password: 'TesteFase13!23');
    expect(result.user.verifiedPhone, isFalse);
    expect(result.devCode, isNotNull);

    api.setToken(result.token);
    final me = await auth.me();
    expect(me.phone, endsWith(newPhone));
    expect(me.verifiedPhone, isFalse);
  });

  test('blocking a user hides them from listBlocks after unblock, and shows up before it', () async {
    final api = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;

    final meAuth = AuthRepository(api);
    final me = await meAuth.register(
      name: 'Bloqueador $tag',
      email: 'bloqueador_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase13!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'client',
      acceptTerms: true,
    );

    final otherAuth = AuthRepository(api);
    final other = await otherAuth.register(
      name: 'Bloqueado $tag',
      email: 'bloqueado_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase13!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'worker',
      acceptTerms: true,
    );

    api.setToken(me.token);
    final chatRepo = ChatRepository(api);
    await chatRepo.blockUser(other.user.id);

    final blocksRepo = BlocksRepository(api);
    final blocksAfterBlock = await blocksRepo.listBlocks();
    expect(blocksAfterBlock.any((b) => b.blockedUserId == other.user.id), isTrue);

    await blocksRepo.unblock(other.user.id);
    final blocksAfterUnblock = await blocksRepo.listBlocks();
    expect(blocksAfterUnblock.any((b) => b.blockedUserId == other.user.id), isFalse);
  });
}
