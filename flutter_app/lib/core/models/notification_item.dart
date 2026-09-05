/// Mirrors the notification documents returned by GET /notifications
/// (backend/routes/public.py's `notify()` writer — no dedicated Pydantic
/// response model on the backend, so this is inferred from the write side
/// and the RN screen's actual usage, not guessed).
class NotificationItem {
  final String id;
  final String title;
  final String body;
  final String type;
  final String? orderId;
  final bool read;
  final String createdAt;

  const NotificationItem({
    required this.id,
    required this.title,
    required this.body,
    required this.type,
    this.orderId,
    required this.read,
    required this.createdAt,
  });

  factory NotificationItem.fromJson(Map<String, dynamic> json) => NotificationItem(
        id: json['id'] as String,
        title: json['title'] as String? ?? '',
        body: json['body'] as String? ?? '',
        type: json['type'] as String? ?? 'default',
        orderId: json['order_id'] as String?,
        read: json['read'] as bool? ?? false,
        createdAt: json['created_at'] as String? ?? '',
      );
}
