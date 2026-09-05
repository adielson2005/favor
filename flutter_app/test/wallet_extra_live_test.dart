// Proves FASE 14 (Testes) coverage of real, previously-untested WalletRepository
// methods — fetchTransactions/fetchOrderPayment/requestWithdrawal/
// fetchWithdrawals/cancelWithdrawal never had a single test before this,
// despite being real money-movement code (see wallet_payment_live_test.dart's
// "never trust frontend for financial values" standard, which the earlier
// gap audit found didn't cover withdrawals at all). Funding a wallet requires
// a real payment gateway this test suite has no admin access to (same
// constraint documented in wallet_payment_live_test.dart), so — like that
// file — this proves the two things provable without funding: a fresh
// wallet's real zero-balance shape, and the backend's real rejection paths.
//
//   flutter test test/wallet_extra_live_test.dart --dart-define=API_BASE_URL=http://localhost:8000
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';

import 'package:fazum/core/errors/api_exception.dart';
import 'package:fazum/core/networking/api_client.dart';
import 'package:fazum/core/repositories/orders_repository.dart';
import 'package:fazum/core/repositories/wallet_repository.dart';
import 'package:fazum/features/auth/data/auth_repository.dart';

const _testCpf = '11144477735';

String _randomPhone() {
  final rand = Random();
  final digits = List.generate(8, (_) => rand.nextInt(10)).join();
  return '949$digits';
}

void main() {
  ApiClient.instance.markAuthReady();

  test('a fresh account has no transactions and no withdrawals', () async {
    final api = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;
    final auth = AuthRepository(api);
    final reg = await auth.register(
      name: 'Carteira Extra $tag',
      email: 'carteira_extra_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase14!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'client',
      acceptTerms: true,
    );
    api.setToken(reg.token);

    final walletRepo = WalletRepository(api);
    expect(await walletRepo.fetchTransactions(), isEmpty);
    expect(await walletRepo.fetchWithdrawals(), isEmpty);
  });

  test('fetchOrderPayment returns null for an order that was never paid', () async {
    final api = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;
    final auth = AuthRepository(api);
    final reg = await auth.register(
      name: 'Sem Pagamento $tag',
      email: 'sem_pagamento_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase14!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'client',
      acceptTerms: true,
    );
    api.setToken(reg.token);

    final order = await OrdersRepository(api).createOrder(
      title: 'Pedido sem pagamento $tag',
      type: 'favor',
      categoryId: 'cat-casa',
      cityId: 'city-parauapebas',
      budget: 40,
    );

    final payment = await WalletRepository(api).fetchOrderPayment(order.id);
    expect(payment, isNull);
  });

  test('requesting a withdrawal above the available balance is rejected with the backend\'s real message', () async {
    final api = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;
    final auth = AuthRepository(api);
    final reg = await auth.register(
      name: 'Saque Sem Saldo $tag',
      email: 'saque_sem_saldo_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase14!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'worker',
      acceptTerms: true,
    );
    api.setToken(reg.token);
    await auth.verifyEmail(reg.devCodeEmail!);
    await auth.verifyPhone(reg.devCodePhone!);

    final walletRepo = WalletRepository(api);
    final account = await walletRepo.addBankAccount(
      holderName: 'Saque Sem Saldo $tag',
      document: _testCpf,
      bankCode: '260',
      agency: '0001',
      accountNumber: '7654321',
      password: 'TesteFase14!23',
    );

    expect(
      () => walletRepo.requestWithdrawal(amount: 50, bankAccountId: account.id, password: 'TesteFase14!23'),
      throwsA(predicate((e) => e is ApiException && e.message.contains('insuficiente'))),
    );
  });

  test('cancelling a withdrawal that doesn\'t exist returns the backend\'s real 404', () async {
    final api = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;
    final auth = AuthRepository(api);
    final reg = await auth.register(
      name: 'Cancela Saque $tag',
      email: 'cancela_saque_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase14!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'worker',
      acceptTerms: true,
    );
    api.setToken(reg.token);

    expect(
      () => WalletRepository(api).cancelWithdrawal('does-not-exist-$tag'),
      throwsA(predicate((e) => e is ApiException && e.message.contains('não encontrado'))),
    );
  });
}
