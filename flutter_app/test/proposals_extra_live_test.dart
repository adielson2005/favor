// Proves FASE 14 (Testes) coverage of ProposalsRepository.cancel — the
// worker-side "withdraw my proposal" action, reachable from real UI
// (order_detail_screen.dart's worker view) but never exercised by a test.
//
//   flutter test test/proposals_extra_live_test.dart --dart-define=API_BASE_URL=http://localhost:8000
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';

import 'package:fazum/core/errors/api_exception.dart';
import 'package:fazum/core/networking/api_client.dart';
import 'package:fazum/core/repositories/orders_repository.dart';
import 'package:fazum/core/repositories/proposals_repository.dart';
import 'package:fazum/features/auth/data/auth_repository.dart';

String _randomPhone() {
  final rand = Random();
  final digits = List.generate(8, (_) => rand.nextInt(10)).join();
  return '949$digits';
}

void main() {
  ApiClient.instance.markAuthReady();

  test('a worker can cancel their own pending proposal, but not twice', () async {
    final api = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;

    final clientAuth = AuthRepository(api);
    final clientReg = await clientAuth.register(
      name: 'Cliente Cancela Proposta $tag',
      email: 'cliente_cp_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase14!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'client',
      acceptTerms: true,
    );
    api.setToken(clientReg.token);
    final order = await OrdersRepository(api).createOrder(
      title: 'Pedido para propor e cancelar $tag',
      type: 'favor',
      categoryId: 'cat-casa',
      cityId: 'city-parauapebas',
      budget: 60,
    );

    final workerAuth = AuthRepository(api);
    final workerReg = await workerAuth.register(
      name: 'Fazedor Cancela Proposta $tag',
      email: 'fazedor_cp_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase14!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'worker',
      acceptTerms: true,
    );
    api.setToken(workerReg.token);
    await workerAuth.verifyEmail(workerReg.devCodeEmail!);
    await workerAuth.verifyPhone(workerReg.devCodePhone!);

    final proposalsRepo = ProposalsRepository(api);
    final proposal = await proposalsRepo.create(orderId: order.id, amount: 55, eta: 'amanhã');

    await proposalsRepo.cancel(proposal.id);
    final proposals = await proposalsRepo.fetchForOrder(order.id);
    expect(proposals.first.status, 'cancelled');

    expect(() => proposalsRepo.cancel(proposal.id), throwsA(isA<ApiException>()));
  });
}
