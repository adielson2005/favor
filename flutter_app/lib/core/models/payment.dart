/// Mirrors frontend/src/api.ts's `Payment` and `Withdrawal` types.
class Payment {
  final String id;
  final String orderId;
  final String clientId;
  final String? workerId;
  final double grossAmount;
  final double commissionAmount;
  final double workerNetAmount;
  final double commissionPercent;
  final String method;
  final String status;
  final String createdAt;

  const Payment({
    required this.id,
    required this.orderId,
    required this.clientId,
    this.workerId,
    required this.grossAmount,
    required this.commissionAmount,
    required this.workerNetAmount,
    required this.commissionPercent,
    required this.method,
    required this.status,
    required this.createdAt,
  });

  factory Payment.fromJson(Map<String, dynamic> json) => Payment(
        id: json['id'] as String,
        orderId: json['order_id'] as String,
        clientId: json['client_id'] as String,
        workerId: json['worker_id'] as String?,
        grossAmount: (json['gross_amount'] as num).toDouble(),
        commissionAmount: (json['commission_amount'] as num).toDouble(),
        workerNetAmount: (json['worker_net_amount'] as num).toDouble(),
        commissionPercent: (json['commission_percent'] as num).toDouble(),
        method: json['method'] as String,
        status: json['status'] as String,
        createdAt: json['created_at'] as String? ?? '',
      );
}

class Withdrawal {
  final String id;
  final double amount;
  final String bankAccountId;
  final String status;
  final String riskLevel;
  final String? reason;
  final String createdAt;

  const Withdrawal({
    required this.id,
    required this.amount,
    required this.bankAccountId,
    required this.status,
    required this.riskLevel,
    this.reason,
    required this.createdAt,
  });

  factory Withdrawal.fromJson(Map<String, dynamic> json) => Withdrawal(
        id: json['id'] as String,
        amount: (json['amount'] as num).toDouble(),
        bankAccountId: json['bank_account_id'] as String,
        status: json['status'] as String,
        riskLevel: json['risk_level'] as String? ?? '',
        reason: json['reason'] as String?,
        createdAt: json['created_at'] as String? ?? '',
      );
}
