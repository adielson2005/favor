/// Mirrors frontend/src/api.ts's `BankAccount` type — only the masked
/// account/document ever reach the client (backend/routes/wallet.py's
/// `mask_account`); the real values stay encrypted server-side.
class BankAccount {
  final String id;
  final String holderName;
  final String bankCode;
  final String agency;
  final String accountType;
  final bool isPrimary;
  final String createdAt;
  final String accountNumberMasked;
  final String documentMasked;

  const BankAccount({
    required this.id,
    required this.holderName,
    required this.bankCode,
    required this.agency,
    required this.accountType,
    required this.isPrimary,
    required this.createdAt,
    required this.accountNumberMasked,
    required this.documentMasked,
  });

  factory BankAccount.fromJson(Map<String, dynamic> json) => BankAccount(
        id: json['id'] as String,
        holderName: json['holder_name'] as String,
        bankCode: json['bank_code'] as String,
        agency: json['agency'] as String,
        accountType: json['account_type'] as String,
        isPrimary: json['is_primary'] as bool? ?? false,
        createdAt: json['created_at'] as String? ?? '',
        accountNumberMasked: json['account_number_masked'] as String? ?? '',
        documentMasked: json['document_masked'] as String? ?? '',
      );
}
