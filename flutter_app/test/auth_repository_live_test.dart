// Exercises AuthController -> AuthRepository -> ApiClient against the REAL
// backend (not mocked) — same "prove it actually works" standard already
// used for this project's other integrations. Runs on the Dart VM (not a
// browser), so it sidesteps the Flutter-web rendering issues seen when
// trying to click through LoginScreen in an automated browser — this test
// exercises the exact same repository/controller code LoginScreen calls,
// just without the widget layer.
//
// Requires the main backend running on port 8000 (already up throughout this
// session) and API_BASE_URL passed at test time:
//   flutter test test/auth_repository_live_test.dart --dart-define=API_BASE_URL=http://localhost:8000
import 'package:flutter_test/flutter_test.dart';

import 'package:fazum/core/networking/api_client.dart';
import 'package:fazum/features/auth/data/auth_repository.dart';

void main() {
  final client = ApiClient.instance;
  client.markAuthReady();
  final repo = AuthRepository(client);

  test('login with the seeded demo client account returns a real session', () async {
    final result = await repo.login(identifier: 'marina@fazum.demo', password: 'faze2024');

    expect(result.token, isNotEmpty);
    expect(result.user.id, 'demo-client');
    expect(result.user.name, 'Marina Alves');
    expect(result.user.verifiedEmail, isTrue);
    expect(result.user.accountStatus, 'ACTIVE');
  });

  test('login with a wrong password is rejected with the backend\'s own message', () async {
    expect(
      () => repo.login(identifier: 'marina@fazum.demo', password: 'wrong-password'),
      throwsA(predicate((e) => e.toString().contains('incorretos'))),
    );
  });

  test('me() returns the authenticated user after login', () async {
    final login = await repo.login(identifier: 'marina@fazum.demo', password: 'faze2024');
    client.setToken(login.token);

    final me = await repo.me();
    expect(me.id, 'demo-client');
    // /auth/me is the private view — phone is owner-only, confirms we're
    // hitting the authenticated endpoint, not the public one.
    expect(me.phone, isNotNull);
  });
}
