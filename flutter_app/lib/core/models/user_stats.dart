/// Mirrors frontend/app/user/[id].tsx's local `UserStats` type — reputation
/// beyond stars, every field derived straight from real orders/proposals
/// (backend/routes/public.py's user_stats — no punctuality field: there's no
/// honest way to compute it, see that endpoint's own docstring).
class UserStats {
  final double? completionRate;
  final int completedCount;
  final int cancelledCount;
  final double? cancellationRateAsWorker;
  final int clientCompletedCount;
  final int clientCancelledCount;
  final double? cancellationRateAsClient;
  final double? repeatClientRate;
  final double? avgResponseHours;

  const UserStats({
    this.completionRate,
    required this.completedCount,
    required this.cancelledCount,
    this.cancellationRateAsWorker,
    required this.clientCompletedCount,
    required this.clientCancelledCount,
    this.cancellationRateAsClient,
    this.repeatClientRate,
    this.avgResponseHours,
  });

  factory UserStats.fromJson(Map<String, dynamic> json) => UserStats(
        completionRate: (json['completion_rate'] as num?)?.toDouble(),
        completedCount: json['completed_count'] as int? ?? 0,
        cancelledCount: json['cancelled_count'] as int? ?? 0,
        cancellationRateAsWorker: (json['cancellation_rate_as_worker'] as num?)?.toDouble(),
        clientCompletedCount: json['client_completed_count'] as int? ?? 0,
        clientCancelledCount: json['client_cancelled_count'] as int? ?? 0,
        cancellationRateAsClient: (json['cancellation_rate_as_client'] as num?)?.toDouble(),
        repeatClientRate: (json['repeat_client_rate'] as num?)?.toDouble(),
        avgResponseHours: (json['avg_response_hours'] as num?)?.toDouble(),
      );
}
