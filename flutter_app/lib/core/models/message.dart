/// Mirrors frontend/src/api.ts's `Message` type.
class ChatMessage {
  final String id;
  final String orderId;
  final String senderId;
  final String type; // "text" | "system" | "image"
  final String text;
  final String? imageB64;
  final String createdAt;
  final String? warning;

  const ChatMessage({
    required this.id,
    required this.orderId,
    required this.senderId,
    required this.type,
    required this.text,
    this.imageB64,
    required this.createdAt,
    this.warning,
  });

  bool get isSystem => type == 'system' || senderId == 'system';

  factory ChatMessage.fromJson(Map<String, dynamic> json) => ChatMessage(
        id: json['id'] as String,
        orderId: json['order_id'] as String,
        senderId: json['sender_id'] as String,
        type: json['type'] as String? ?? 'text',
        text: json['text'] as String? ?? '',
        imageB64: json['image_b64'] as String?,
        createdAt: json['created_at'] as String? ?? '',
        warning: json['warning'] as String?,
      );
}
