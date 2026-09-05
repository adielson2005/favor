import '../models/message.dart';
import '../networking/api_client.dart';

/// Mirrors backend/routes/public.py's chat + moderation endpoints used from
/// the chat screen (report/block live here too since chat is their only
/// caller so far — same as frontend/app/chat/[id].tsx calling api.post
/// directly rather than through a dedicated moderation module).
class ChatRepository {
  ChatRepository(this._client);
  final ApiClient _client;

  Future<List<ChatMessage>> fetchMessages(String orderId) async {
    final json = await _client.get<List<dynamic>>('/orders/$orderId/messages');
    return json.map((m) => ChatMessage.fromJson(m as Map<String, dynamic>)).toList();
  }

  /// Returns the just-sent message (including a `warning` field if the
  /// backend's external-payment detector flagged it — non-blocking, the
  /// message still sends).
  Future<ChatMessage> sendMessage(String orderId, {String text = '', String? imageB64}) async {
    final json = await _client.post<Map<String, dynamic>>('/orders/$orderId/messages', body: {
      'text': text,
      'image_b64': imageB64,
    });
    return ChatMessage.fromJson(json);
  }

  Future<void> reportTarget({required String targetType, required String targetId, required String reason}) =>
      _client.post('/reports', body: {'target_type': targetType, 'target_id': targetId, 'reason': reason});

  Future<void> blockUser(String userId) => _client.post('/blocks', body: {'blocked_user_id': userId});
}
