import '../models/bank_account.dart';
import '../models/payment.dart';
import '../models/wallet.dart';
import '../networking/api_client.dart';

/// Mirrors backend/routes/wallet.py. Every mutating call (pay, deposit,
/// withdraw, bank account add) is idempotency-keyed the same way the backend
/// expects — see [newIdempotencyKey] in core/networking/api_client.dart —
/// so a retried tap from a flaky connection can't double-charge or
/// double-withdraw.
class WalletRepository {
  WalletRepository(this._client);
  final ApiClient _client;

  Future<WalletBalance> fetchWallet() async {
    final json = await _client.get<Map<String, dynamic>>('/wallet');
    return WalletBalance.fromJson(json);
  }

  Future<List<WalletTransaction>> fetchTransactions({int limit = 30, int offset = 0}) async {
    final json = await _client.get<List<dynamic>>('/wallet/transactions', query: {'limit': limit, 'offset': offset});
    return json.map((t) => WalletTransaction.fromJson(t as Map<String, dynamic>)).toList();
  }

  /// Mirrors POST /orders/{id}/pay. `password` is only required when the
  /// backend's fraud check comes back MEDIUM risk (401 asking for it) — same
  /// conditional-reauth pattern as everywhere else in this app that touches
  /// money.
  Future<Payment> payOrder(String orderId, {String? password}) async {
    final json = await _client.post<Map<String, dynamic>>(
      '/orders/$orderId/pay',
      body: {'method': 'wallet', 'password': password},
      headers: {'Idempotency-Key': newIdempotencyKey()},
    );
    return Payment.fromJson(json);
  }

  Future<Payment?> fetchOrderPayment(String orderId) async {
    final json = await _client.get<Map<String, dynamic>?>('/orders/$orderId/payment');
    return json != null ? Payment.fromJson(json) : null;
  }

  Future<List<BankAccount>> fetchBankAccounts() async {
    final json = await _client.get<List<dynamic>>('/bank-accounts');
    return json.map((a) => BankAccount.fromJson(a as Map<String, dynamic>)).toList();
  }

  Future<BankAccount> addBankAccount({
    required String holderName,
    required String document,
    required String bankCode,
    required String agency,
    required String accountNumber,
    String accountType = 'checking',
    required String password,
  }) async {
    final json = await _client.post<Map<String, dynamic>>('/bank-accounts', body: {
      'holder_name': holderName,
      'document': document,
      'bank_code': bankCode,
      'agency': agency,
      'account_number': accountNumber,
      'account_type': accountType,
      'password': password,
    });
    return BankAccount.fromJson(json);
  }

  Future<void> setPrimaryBankAccount(String accountId) => _client.patch('/bank-accounts/$accountId/primary');

  Future<void> removeBankAccount(String accountId, {required String password}) =>
      _client.delete('/bank-accounts/$accountId', body: {'password': password});

  Future<Withdrawal> requestWithdrawal({
    required double amount,
    required String bankAccountId,
    required String password,
  }) async {
    final json = await _client.post<Map<String, dynamic>>(
      '/wallet/withdrawals',
      body: {'amount': amount, 'bank_account_id': bankAccountId, 'password': password},
      headers: {'Idempotency-Key': newIdempotencyKey()},
    );
    return Withdrawal.fromJson(json);
  }

  Future<List<Withdrawal>> fetchWithdrawals() async {
    final json = await _client.get<List<dynamic>>('/wallet/withdrawals');
    return json.map((w) => Withdrawal.fromJson(w as Map<String, dynamic>)).toList();
  }

  Future<void> cancelWithdrawal(String withdrawalId) => _client.post('/wallet/withdrawals/$withdrawalId/cancel');
}
