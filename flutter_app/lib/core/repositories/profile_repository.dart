import '../models/review.dart';
import '../models/user.dart';
import '../models/user_stats.dart';
import '../networking/api_client.dart';

/// Mirrors backend/routes/public.py's user profile endpoints — GET
/// /users/{id} returns the public shape for anyone; PATCH only succeeds for
/// the account owner (or an admin), enforced server-side regardless of what
/// this client sends.
class ProfileRepository {
  ProfileRepository(this._client);
  final ApiClient _client;

  Future<AppUser> fetchUser(String userId) async {
    final json = await _client.get<Map<String, dynamic>>('/users/$userId');
    return AppUser.fromJson(json);
  }

  Future<UserStats> fetchStats(String userId) async {
    final json = await _client.get<Map<String, dynamic>>('/users/$userId/stats');
    return UserStats.fromJson(json);
  }

  Future<List<Review>> fetchReviews(String userId) async {
    final json = await _client.get<List<dynamic>>('/users/$userId/reviews');
    return json.map((r) => Review.fromJson(r as Map<String, dynamic>)).toList();
  }

  Future<AppUser> updateProfile(
    String userId, {
    String? name,
    String? bio,
    String? cityId,
    String? neighborhoodId,
    String? avatarB64,
  }) async {
    final json = await _client.patch<Map<String, dynamic>>('/users/$userId', body: {
      'name': ?name,
      'bio': ?bio,
      'city_id': ?cityId,
      'neighborhood_id': ?neighborhoodId,
      'avatar_b64': ?avatarB64,
    });
    return AppUser.fromJson(json);
  }
}
