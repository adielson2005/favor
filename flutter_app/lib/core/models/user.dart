/// Mirrors frontend/src/api.ts's `User` type. The private-only fields (phone,
/// account_status, has_password, etc.) are only ever present on the account
/// owner's own view (backend's `private_user()`, never `public_user()`) — see
/// backend/routes/public.py. Kept nullable here for exactly that reason, not
/// because the data is unreliable.
class AppUser {
  final String id;
  final String name;
  final String initials;
  final String? bio;
  final double rating;
  final int ratingCount;
  final int jobsDone;
  final bool verifiedIdentity;
  final bool verifiedEmail;
  final bool verifiedPhone;
  final String level;
  final String? memberSince;
  final bool? isAdmin;
  final String? neighborhoodId;
  final String? cityId;
  final String? stateId;
  final String? preference; // "client" | "worker" | "both"
  final String? avatarB64;

  // Owner-only fields — null when viewing someone else's profile.
  final String? phone;
  final String? emailVerifiedAt;
  final String? phoneVerifiedAt;
  final String? accountStatus;
  final bool? hasPassword;

  const AppUser({
    required this.id,
    required this.name,
    required this.initials,
    this.bio,
    required this.rating,
    required this.ratingCount,
    required this.jobsDone,
    required this.verifiedIdentity,
    required this.verifiedEmail,
    required this.verifiedPhone,
    required this.level,
    this.memberSince,
    this.isAdmin,
    this.neighborhoodId,
    this.cityId,
    this.stateId,
    this.preference,
    this.avatarB64,
    this.phone,
    this.emailVerifiedAt,
    this.phoneVerifiedAt,
    this.accountStatus,
    this.hasPassword,
  });

  factory AppUser.fromJson(Map<String, dynamic> json) => AppUser(
        id: json['id'] as String,
        name: json['name'] as String,
        initials: json['initials'] as String? ?? '',
        bio: json['bio'] as String?,
        rating: (json['rating'] as num?)?.toDouble() ?? 0,
        ratingCount: json['rating_count'] as int? ?? 0,
        jobsDone: json['jobs_done'] as int? ?? 0,
        verifiedIdentity: json['verified_identity'] as bool? ?? false,
        verifiedEmail: json['verified_email'] as bool? ?? false,
        verifiedPhone: json['verified_phone'] as bool? ?? false,
        level: json['level'] as String? ?? 'Novo',
        memberSince: json['member_since'] as String?,
        isAdmin: json['is_admin'] as bool?,
        neighborhoodId: json['neighborhood_id'] as String?,
        cityId: json['city_id'] as String?,
        stateId: json['state_id'] as String?,
        preference: json['preference'] as String?,
        avatarB64: json['avatar_b64'] as String?,
        phone: json['phone'] as String?,
        emailVerifiedAt: json['email_verified_at'] as String?,
        phoneVerifiedAt: json['phone_verified_at'] as String?,
        accountStatus: json['account_status'] as String?,
        hasPassword: json['has_password'] as bool?,
      );
}
