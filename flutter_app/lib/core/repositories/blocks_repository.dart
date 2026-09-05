import '../models/user.dart';
import '../networking/api_client.dart';

class BlockedUser {
  final String blockedUserId;
  final AppUser? user;

  const BlockedUser({required this.blockedUserId, this.user});

  factory BlockedUser.fromJson(Map<String, dynamic> json) => BlockedUser(
        blockedUserId: json['blocked_user_id'] as String,
        user: json['user'] != null ? AppUser.fromJson(json['user'] as Map<String, dynamic>) : null,
      );
}

/// Mirrors backend/routes/public.py's block/unblock endpoints — blocking is
/// mutual (assert_not_blocked checks both directions), so unblocking here is
/// the only way either side can interact again.
class BlocksRepository {
  BlocksRepository(this._client);
  final ApiClient _client;

  Future<List<BlockedUser>> listBlocks() async {
    final json = await _client.get<List<dynamic>>('/blocks');
    return json.map((b) => BlockedUser.fromJson(b as Map<String, dynamic>)).toList();
  }

  Future<void> unblock(String blockedUserId) =>
      _client.delete<Map<String, dynamic>>('/blocks/$blockedUserId');
}
