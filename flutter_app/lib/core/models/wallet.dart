/// Mirrors frontend/src/api.ts's `Wallet` type — money as reais (double),
/// same as every other JSON boundary in this app; only the backend's
/// internal ledger uses integer centavos.
class WalletBalance {
  final double available;
  final double pending;
  final double processing;
  final double totalReceived;
  final double totalSpent;
  final String currency;

  const WalletBalance({
    required this.available,
    required this.pending,
    required this.processing,
    required this.totalReceived,
    required this.totalSpent,
    required this.currency,
  });

  factory WalletBalance.fromJson(Map<String, dynamic> json) => WalletBalance(
        available: (json['available'] as num?)?.toDouble() ?? 0,
        pending: (json['pending'] as num?)?.toDouble() ?? 0,
        processing: (json['processing'] as num?)?.toDouble() ?? 0,
        totalReceived: (json['total_received'] as num?)?.toDouble() ?? 0,
        totalSpent: (json['total_spent'] as num?)?.toDouble() ?? 0,
        currency: json['currency'] as String? ?? 'BRL',
      );
}

/// Mirrors frontend/src/api.ts's `WalletTransaction` type — one row per
/// ledger entry (backend/wallet.py never mutates balance without appending
/// one of these), never a synthesized/derived view.
class WalletTransaction {
  final String id;
  final String type;
  final double amount;
  final String direction; // IN | OUT | MOVE
  final String status;
  final String bucket;
  final String referenceType;
  final String referenceId;
  final String description;
  final String createdAt;
  final String? provider;
  final String? providerTransactionId;

  const WalletTransaction({
    required this.id,
    required this.type,
    required this.amount,
    required this.direction,
    required this.status,
    required this.bucket,
    required this.referenceType,
    required this.referenceId,
    required this.description,
    required this.createdAt,
    this.provider,
    this.providerTransactionId,
  });

  factory WalletTransaction.fromJson(Map<String, dynamic> json) => WalletTransaction(
        id: json['id'] as String,
        type: json['type'] as String,
        amount: (json['amount'] as num).toDouble(),
        direction: json['direction'] as String,
        status: json['status'] as String,
        bucket: json['bucket'] as String? ?? '',
        referenceType: json['reference_type'] as String? ?? '',
        referenceId: json['reference_id'] as String? ?? '',
        description: json['description'] as String? ?? '',
        createdAt: json['created_at'] as String? ?? '',
        provider: json['provider'] as String?,
        providerTransactionId: json['provider_transaction_id'] as String?,
      );
}
