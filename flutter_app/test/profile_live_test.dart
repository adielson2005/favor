// Proves FASE 12 (Perfil/reputação) end-to-end against the REAL backend —
// same standard as order_lifecycle_live_test.dart. Drives a full
// order -> completed -> review flow so fetchStats/fetchReviews return real,
// non-zero data (not just the empty/zero shape a brand-new account gets),
// and confirms updateProfile actually persists via a fresh fetchUser.
//
//   flutter test test/profile_live_test.dart --dart-define=API_BASE_URL=http://localhost:8000
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';

import 'package:fazum/core/networking/api_client.dart';
import 'package:fazum/core/repositories/orders_repository.dart';
import 'package:fazum/core/repositories/profile_repository.dart';
import 'package:fazum/core/repositories/proposals_repository.dart';
import 'package:fazum/features/auth/data/auth_repository.dart';

String _randomPhone() {
  final rand = Random();
  final digits = List.generate(8, (_) => rand.nextInt(10)).join();
  return '949$digits';
}

void main() {
  ApiClient.instance.markAuthReady();

  test('fresh account has zero-safe stats and no reviews', () async {
    final api = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;
    final auth = AuthRepository(api);
    final reg = await auth.register(
      name: 'Perfil Novo $tag',
      email: 'perfilnovo_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase12!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'client',
      acceptTerms: true,
    );
    api.setToken(reg.token);

    final profileRepo = ProfileRepository(api);
    final stats = await profileRepo.fetchStats(reg.user.id);
    expect(stats.completedCount, 0);
    expect(stats.cancelledCount, 0);

    final reviews = await profileRepo.fetchReviews(reg.user.id);
    expect(reviews, isEmpty);
  });

  test('updateProfile persists name/bio and is visible via fetchUser', () async {
    final api = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;
    final auth = AuthRepository(api);
    final reg = await auth.register(
      name: 'Antes Editar $tag',
      email: 'antes_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase12!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'client',
      acceptTerms: true,
    );
    api.setToken(reg.token);

    final profileRepo = ProfileRepository(api);
    final updated = await profileRepo.updateProfile(reg.user.id, name: 'Depois Editar $tag', bio: 'Bio de teste $tag');
    expect(updated.name, 'Depois Editar $tag');
    expect(updated.bio, 'Bio de teste $tag');

    final fetched = await profileRepo.fetchUser(reg.user.id);
    expect(fetched.name, 'Depois Editar $tag');
    expect(fetched.bio, 'Bio de teste $tag');
  });

  test('a completed order with a real review shows up in the worker\'s stats and reviews', () async {
    final api = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;

    final clientAuth = AuthRepository(api);
    final clientReg = await clientAuth.register(
      name: 'Cliente Fase12 $tag',
      email: 'cliente12_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase12!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'client',
      acceptTerms: true,
    );
    api.setToken(clientReg.token);

    final ordersRepo = OrdersRepository(api);
    final order = await ordersRepo.createOrder(
      title: 'Trocar uma torneira $tag',
      description: 'Vazamento na cozinha.',
      type: 'servico',
      categoryId: 'cat-casa',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      budget: 90,
    );

    final workerAuth = AuthRepository(api);
    final workerReg = await workerAuth.register(
      name: 'Fazedor Fase12 $tag',
      email: 'fazedor12_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase12!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'worker',
      acceptTerms: true,
    );
    api.setToken(workerReg.token);
    await workerAuth.verifyEmail(workerReg.devCodeEmail!);
    await workerAuth.verifyPhone(workerReg.devCodePhone!);

    final proposalsRepo = ProposalsRepository(api);
    final proposal = await proposalsRepo.create(orderId: order.id, amount: 80, eta: 'hoje à tarde');

    api.setToken(clientReg.token);
    await proposalsRepo.accept(proposal.id);

    api.setToken(workerReg.token);
    await ordersRepo.start(order.id);
    await ordersRepo.requestCompletion(order.id);

    api.setToken(clientReg.token);
    await ordersRepo.complete(order.id);

    await api.post<Map<String, dynamic>>('/reviews', body: {
      'order_id': order.id,
      'to_id': workerReg.user.id,
      'stars': 5,
      'comment': 'Ótimo serviço, recomendo! $tag',
    });

    final profileRepo = ProfileRepository(api);
    final stats = await profileRepo.fetchStats(workerReg.user.id);
    expect(stats.completedCount, greaterThanOrEqualTo(1));
    expect(stats.completionRate, isNotNull);

    final reviews = await profileRepo.fetchReviews(workerReg.user.id);
    expect(reviews, isNotEmpty);
    final review = reviews.firstWhere((r) => r.comment == 'Ótimo serviço, recomendo! $tag');
    expect(review.stars, 5);
    expect(review.author?.id, clientReg.user.id);

    final workerProfile = await profileRepo.fetchUser(workerReg.user.id);
    expect(workerProfile.ratingCount, greaterThanOrEqualTo(1));
  });
}
