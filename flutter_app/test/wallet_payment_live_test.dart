// Proves FASE 10 slice 1 (wallet balance + order payment) against the REAL
// backend. Doesn't fund a test wallet (that needs admin credentials this
// suite doesn't have) — instead proves the two things that don't need
// funding: a fresh account's wallet genuinely starts at zero, and paying
// with insufficient balance is correctly rejected with the backend's own
// error, not silently accepted or a generic 500.
//
//   flutter test test/wallet_payment_live_test.dart --dart-define=API_BASE_URL=http://localhost:8000
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';

import 'package:fazum/core/errors/api_exception.dart';
import 'package:fazum/core/networking/api_client.dart';
import 'package:fazum/core/repositories/orders_repository.dart';
import 'package:fazum/core/repositories/proposals_repository.dart';
import 'package:fazum/core/repositories/wallet_repository.dart';
import 'package:fazum/features/auth/data/auth_repository.dart';

String _randomPhone() {
  final rand = Random();
  final digits = List.generate(8, (_) => rand.nextInt(10)).join();
  return '949$digits';
}

void main() {
  ApiClient.instance.markAuthReady();

  test('a fresh account has a zero balance wallet', () async {
    final api = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;

    final auth = AuthRepository(api);
    final reg = await auth.register(
      name: 'Cliente Carteira $tag',
      email: 'carteira_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase10!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'client',
      acceptTerms: true,
    );
    api.setToken(reg.token);

    final wallet = await WalletRepository(api).fetchWallet();
    expect(wallet.available, 0);
    expect(wallet.pending, 0);
    expect(wallet.currency, 'BRL');
  });

  test('paying for an accepted order with insufficient balance is rejected', () async {
    final api = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;

    final clientAuth = AuthRepository(api);
    final clientReg = await clientAuth.register(
      name: 'Cliente SemSaldo $tag',
      email: 'semsaldo_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase10!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'client',
      acceptTerms: true,
    );
    api.setToken(clientReg.token);

    // pay_order requires an ACTIVE account too (require_active_account),
    // same gate discovered for create_proposal in FASE 7 — the client also
    // needs email+phone verified before paying, not just the worker.
    await clientAuth.verifyEmail(clientReg.devCodeEmail!);
    await clientAuth.verifyPhone(clientReg.devCodePhone!);

    final ordersRepo = OrdersRepository(api);
    final order = await ordersRepo.createOrder(
      title: 'Pedido para pagar $tag',
      type: 'favor',
      categoryId: 'cat-casa',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      budget: 100,
    );

    final workerAuth = AuthRepository(api);
    final workerReg = await workerAuth.register(
      name: 'Fazedor SemSaldo $tag',
      email: 'fazedorsemsaldo_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase10!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'worker',
      acceptTerms: true,
    );
    api.setToken(workerReg.token);
    await workerAuth.verifyEmail(workerReg.devCodeEmail!);
    await workerAuth.verifyPhone(workerReg.devCodePhone!);

    final proposalsRepo = ProposalsRepository(api);
    final proposal = await proposalsRepo.create(orderId: order.id, amount: 90, eta: 'hoje');

    api.setToken(clientReg.token);
    await proposalsRepo.accept(proposal.id);

    final walletRepo = WalletRepository(api);
    expect(
      () => walletRepo.payOrder(order.id),
      throwsA(predicate((e) => e is ApiException && e.message.toLowerCase().contains('saldo insuficiente'))),
    );
  });
}
