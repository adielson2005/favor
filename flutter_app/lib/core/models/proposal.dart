import 'user.dart';

/// Mirrors frontend/src/api.ts's `Proposal` type.
class Proposal {
  final String id;
  final String orderId;
  final String workerId;
  final double amount;
  final String message;
  final String eta;
  final String status; // pending | accepted | rejected | cancelled
  final AppUser? worker;

  const Proposal({
    required this.id,
    required this.orderId,
    required this.workerId,
    required this.amount,
    required this.message,
    required this.eta,
    required this.status,
    this.worker,
  });

  factory Proposal.fromJson(Map<String, dynamic> json) => Proposal(
        id: json['id'] as String,
        orderId: json['order_id'] as String,
        workerId: json['worker_id'] as String,
        amount: (json['amount'] as num).toDouble(),
        message: json['message'] as String? ?? '',
        eta: json['eta'] as String? ?? '',
        status: json['status'] as String,
        worker: json['worker'] != null ? AppUser.fromJson(json['worker'] as Map<String, dynamic>) : null,
      );
}
