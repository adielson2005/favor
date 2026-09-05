// Proves FASE 8 (Contratação) end-to-end against the REAL backend — same
// standard as proposals_flow_live_test.dart, extended past "accepted" through
// the rest of the state machine: accepted → in_progress →
// completion_requested → completed.
//
//   flutter test test/order_lifecycle_live_test.dart --dart-define=API_BASE_URL=http://localhost:8000
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';

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

  test('accepted order moves through in_progress -> completion_requested -> completed', () async {
    final api = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;

    final clientAuth = AuthRepository(api);
    final clientReg = await clientAuth.register(
      name: 'Cliente Fase8 $tag',
      email: 'cliente8_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase8!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'client',
      acceptTerms: true,
    );
    api.setToken(clientReg.token);

    final ordersRepo = OrdersRepository(api);
    final order = await ordersRepo.createOrder(
      title: 'Pintar uma parede $tag',
      description: 'Parede de 3x2,5m, tinta já comprada.',
      type: 'servico',
      categoryId: 'cat-casa',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      budget: 150,
    );

    final workerAuth = AuthRepository(api);
    final workerReg = await workerAuth.register(
      name: 'Fazedor Fase8 $tag',
      email: 'fazedor8_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase8!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'worker',
      acceptTerms: true,
    );
    api.setToken(workerReg.token);
    await workerAuth.verifyEmail(workerReg.devCodeEmail!);
    await workerAuth.verifyPhone(workerReg.devCodePhone!);

    final proposalsRepo = ProposalsRepository(api);
    final proposal = await proposalsRepo.create(orderId: order.id, amount: 140, eta: 'amanhã de manhã');

    api.setToken(clientReg.token);
    await proposalsRepo.accept(proposal.id);
    final accepted = await ordersRepo.fetchOrder(order.id);
    expect(accepted.status, 'accepted');

    // Worker starts the service.
    api.setToken(workerReg.token);
    await ordersRepo.start(order.id);
    final started = await ordersRepo.fetchOrder(order.id);
    expect(started.status, 'in_progress');

    // Worker signals completion.
    await ordersRepo.requestCompletion(order.id);
    final requested = await ordersRepo.fetchOrder(order.id);
    expect(requested.status, 'completion_requested');

    // Client has the final say.
    api.setToken(clientReg.token);
    await ordersRepo.complete(order.id);
    final completed = await ordersRepo.fetchOrder(order.id);
    expect(completed.status, 'completed');
  });

  test('a published order can be cancelled by its client', () async {
    final api = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;

    final clientAuth = AuthRepository(api);
    final clientReg = await clientAuth.register(
      name: 'Cliente Cancela $tag',
      email: 'cancela_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase8!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'client',
      acceptTerms: true,
    );
    api.setToken(clientReg.token);

    final ordersRepo = OrdersRepository(api);
    final order = await ordersRepo.createOrder(
      title: 'Pedido que vai ser cancelado $tag',
      type: 'favor',
      categoryId: 'cat-casa',
      cityId: 'city-parauapebas',
      budget: 50,
    );

    await ordersRepo.cancel(order.id);
    final cancelled = await ordersRepo.fetchOrder(order.id);
    expect(cancelled.status, 'cancelled');
  });
}
