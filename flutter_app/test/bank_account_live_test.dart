// Proves FASE 10 slice 2 (bank accounts CRUD) against the REAL backend.
// Uses '11144477735', a checksum-valid fictitious CPF commonly used in
// Brazilian dev/test contexts — never a real person's document.
//
//   flutter test test/bank_account_live_test.dart --dart-define=API_BASE_URL=http://localhost:8000
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';

import 'package:fazum/core/networking/api_client.dart';
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

  test('add, set primary, and remove a bank account', () async {
    final api = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;

    final auth = AuthRepository(api);
    final reg = await auth.register(
      name: 'Conta Bancaria Teste $tag',
      email: 'contabancaria_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase10b!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'worker',
      acceptTerms: true,
    );
    api.setToken(reg.token);
    await auth.verifyEmail(reg.devCodeEmail!);
    await auth.verifyPhone(reg.devCodePhone!);

    final walletRepo = WalletRepository(api);

    final initial = await walletRepo.fetchBankAccounts();
    expect(initial, isEmpty);

    final added = await walletRepo.addBankAccount(
      holderName: 'Conta Bancaria Teste $tag',
      document: _testCpf,
      bankCode: '260',
      agency: '0001',
      accountNumber: '1234567',
      password: 'TesteFase10b!23',
    );
    expect(added.accountNumberMasked, endsWith('4567'));
    expect(added.documentMasked, endsWith('35'));
    expect(added.isPrimary, isTrue); // first account is always primary

    final afterAdd = await walletRepo.fetchBankAccounts();
    expect(afterAdd.length, 1);
    expect(afterAdd.first.id, added.id);

    await walletRepo.setPrimaryBankAccount(added.id);
    final afterSetPrimary = await walletRepo.fetchBankAccounts();
    expect(afterSetPrimary.first.isPrimary, isTrue);

    await walletRepo.removeBankAccount(added.id, password: 'TesteFase10b!23');
    final afterRemove = await walletRepo.fetchBankAccounts();
    expect(afterRemove, isEmpty);
  });
}
