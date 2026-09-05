import 'user.dart';

/// Mirrors frontend/app/user/[id].tsx's local `Review` type.
class Review {
  final String id;
  final int stars;
  final String? comment;
  final AppUser? author;

  const Review({required this.id, required this.stars, this.comment, this.author});

  factory Review.fromJson(Map<String, dynamic> json) => Review(
        id: json['id'] as String,
        stars: json['stars'] as int? ?? 0,
        comment: json['comment'] as String?,
        author: json['author'] != null ? AppUser.fromJson(json['author'] as Map<String, dynamic>) : null,
      );
}
