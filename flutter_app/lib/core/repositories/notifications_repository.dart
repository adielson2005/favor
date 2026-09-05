import '../models/notification_item.dart';
import '../networking/api_client.dart';

/// Mirrors GET /notifications and POST /notifications/read
/// (backend/routes/public.py). Both the unread-count-only need (Home's bell)
/// and the full list (FASE 11's NotificationsScreen) go through here now.
class NotificationsRepository {
  NotificationsRepository(this._client);
  final ApiClient _client;

  Future<int> fetchUnreadCount() async {
    final json = await _client.get<Map<String, dynamic>>('/notifications');
    return json['unread'] as int? ?? 0;
  }

  Future<List<NotificationItem>> fetchNotifications({int limit = 50, int offset = 0}) async {
    final json = await _client.get<Map<String, dynamic>>('/notifications', query: {'limit': limit, 'offset': offset});
    final items = json['items'] as List<dynamic>? ?? [];
    return items.map((n) => NotificationItem.fromJson(n as Map<String, dynamic>)).toList();
  }

  /// Marks every notification read — same "mark all, not one" behavior as
  /// backend/routes/public.py's `read_notifications` (there's no per-item
  /// read endpoint).
  Future<void> markAllRead() => _client.post('/notifications/read');
}
