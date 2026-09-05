// Proves FASE 7 (Sistema de propostas) end-to-end against the REAL backend —
// same "hit the real API, don't mock" standard as auth_repository_live_test.dart.
// Registers two fresh throwaway accounts (client + worker), publishes a real
// order, submits a real proposal, accepts it, and confirms the order's
// status/worker_id actually transitioned server-side.
//
//   flutter test test/proposals_flow_live_test.dart --dart-define=API_BASE_URL=http://localhost:8000
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';

import 'package:fazum/core/networking/api_client.dart';
import 'package:fazum/features/auth/data/auth_repository.dart';
import 'package:fazum/core/repositories/orders_repository.dart';
import 'package:fazum/core/repositories/proposals_repository.dart';

String _randomPhone() {
  final rand = Random();
  final digits = List.generate(8, (_) => rand.nextInt(10)).join();
  return '949$digits';
}

void main() {
  ApiClient.instance.markAuthReady();

  test('client publishes an order, worker proposes, client accepts — full round trip', () async {
    // Two separate ApiClient-backed repositories so the client and worker
    // sessions never share a bearer token mid-test.
    final clientApi = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;

    final clientAuth = AuthRepository(clientApi);
    final clientReg = await clientAuth.register(
      name: 'Cliente Teste $tag',
      email: 'cliente_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase7!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'client',
      acceptTerms: true,
    );

    clientApi.setToken(clientReg.token);
    final ordersRepo = OrdersRepository(clientApi);
    final order = await ordersRepo.createOrder(
      title: 'Preciso de ajuda para montar uma estante $tag',
      description: 'Estante de 4 prateleiras, já tenho as peças.',
      type: 'favor',
      categoryId: 'cat-casa',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      budget: 80,
    );
    expect(order.status, 'published');
    expect(order.clientId, isNotEmpty);

    final proposalsRepoAsClient = ProposalsRepository(clientApi);

    // Switch the SAME ApiClient to a worker session to submit the proposal —
    // mirrors how a real device only ever holds one session at a time; we
    // just swap tokens instead of standing up two app instances.
    final workerAuth = AuthRepository(clientApi);
    final workerReg = await workerAuth.register(
      name: 'Fazedor Teste $tag',
      email: 'fazedor_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase7!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'worker',
      acceptTerms: true,
    );
    clientApi.setToken(workerReg.token);

    // create_proposal requires an ACTIVE account (backend/verification.py's
    // require_active_account) — a fresh registration starts as
    // PENDING_VERIFICATION until both email and phone are confirmed. The
    // dev_code_email/dev_code_phone fields exist specifically because SMTP/SMS
    // aren't configured in this environment (register() returns the code
    // directly instead of actually sending it) — using them here is the same
    // "prove it actually works" standard as every other live test, not a
    // shortcut around the real gate.
    expect(workerReg.devCodeEmail, isNotNull);
    expect(workerReg.devCodePhone, isNotNull);
    await workerAuth.verifyEmail(workerReg.devCodeEmail!);
    await workerAuth.verifyPhone(workerReg.devCodePhone!);

    final proposalsRepoAsWorker = ProposalsRepository(clientApi);
    final proposal = await proposalsRepoAsWorker.create(
      orderId: order.id,
      amount: 70,
      eta: 'hoje à tarde',
      message: 'Já montei várias estantes parecidas, posso ir agora.',
    );
    expect(proposal.status, 'pending');
    expect(proposal.orderId, order.id);

    // Back to the client session to see and accept the proposal.
    clientApi.setToken(clientReg.token);
    final proposalsForClient = await proposalsRepoAsClient.fetchForOrder(order.id);
    expect(proposalsForClient.any((p) => p.id == proposal.id), isTrue);
    expect(proposalsForClient.first.worker?.name, contains('Fazedor Teste'));

    await proposalsRepoAsClient.accept(proposal.id);

    final acceptedOrder = await ordersRepo.fetchOrder(order.id);
    expect(acceptedOrder.status, 'accepted');
    expect(acceptedOrder.workerId, isNotEmpty);
    expect(acceptedOrder.acceptedAmount, 70);
  });
}
