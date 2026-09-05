import 'user.dart';

/// Embedded category snapshot on an order (backend denormalizes id/name/icon
/// at read time — see backend/routes/public.py's order shaping) — not the
/// same as core/models/geo.dart's `Category` (that one includes
/// subcategories and `active`, this one is just the display snapshot).
class OrderCategorySnapshot {
  final String id;
  final String name;
  final String icon;
  const OrderCategorySnapshot({required this.id, required this.name, required this.icon});

  factory OrderCategorySnapshot.fromJson(Map<String, dynamic> json) => OrderCategorySnapshot(
        id: json['id'] as String,
        name: json['name'] as String,
        icon: json['icon'] as String,
      );
}

/// Mirrors frontend/src/api.ts's `Order` type field-for-field.
class Order {
  final String id;
  final String title;
  final String description;
  final String type; // "favor" | "servico"
  final OrderCategorySnapshot category;
  final String? subcategory;
  final String categoryId;
  final String? subcategoryId;
  final String cityId;
  final String? neighborhoodId;
  final String? neighborhood;
  final String? city;
  final String dateLabel;
  final String timeLabel;
  final double budget;
  final String status;
  final String statusLabel;
  final String clientId;
  final String? workerId;
  final AppUser? client;
  final AppUser? worker;
  final int proposalsCount;
  final Map<String, String> fields;
  final double? acceptedAmount;
  final bool reviewedByClient;
  final bool reviewedByWorker;
  final String createdAt;
  final bool urgent;
  final String recurrence; // "none" | "weekly" | "biweekly" | "monthly"

  const Order({
    required this.id,
    required this.title,
    required this.description,
    required this.type,
    required this.category,
    this.subcategory,
    required this.categoryId,
    this.subcategoryId,
    required this.cityId,
    this.neighborhoodId,
    this.neighborhood,
    this.city,
    required this.dateLabel,
    required this.timeLabel,
    required this.budget,
    required this.status,
    required this.statusLabel,
    required this.clientId,
    this.workerId,
    this.client,
    this.worker,
    required this.proposalsCount,
    required this.fields,
    this.acceptedAmount,
    required this.reviewedByClient,
    required this.reviewedByWorker,
    required this.createdAt,
    required this.urgent,
    required this.recurrence,
  });

  factory Order.fromJson(Map<String, dynamic> json) => Order(
        id: json['id'] as String,
        title: json['title'] as String,
        description: json['description'] as String? ?? '',
        type: json['type'] as String? ?? 'favor',
        category: OrderCategorySnapshot.fromJson(json['category'] as Map<String, dynamic>),
        subcategory: json['subcategory'] as String?,
        categoryId: json['category_id'] as String,
        subcategoryId: json['subcategory_id'] as String?,
        cityId: json['city_id'] as String,
        neighborhoodId: json['neighborhood_id'] as String?,
        neighborhood: json['neighborhood'] as String?,
        city: json['city'] as String?,
        dateLabel: json['date_label'] as String? ?? '',
        timeLabel: json['time_label'] as String? ?? '',
        budget: (json['budget'] as num?)?.toDouble() ?? 0,
        status: json['status'] as String,
        statusLabel: json['status_label'] as String? ?? json['status'] as String,
        clientId: json['client_id'] as String,
        workerId: json['worker_id'] as String?,
        client: json['client'] != null ? AppUser.fromJson(json['client'] as Map<String, dynamic>) : null,
        worker: json['worker'] != null ? AppUser.fromJson(json['worker'] as Map<String, dynamic>) : null,
        proposalsCount: json['proposals_count'] as int? ?? 0,
        fields: (json['fields'] as Map<String, dynamic>? ?? {}).map((k, v) => MapEntry(k, v.toString())),
        acceptedAmount: (json['accepted_amount'] as num?)?.toDouble(),
        reviewedByClient: json['reviewed_by_client'] as bool? ?? false,
        reviewedByWorker: json['reviewed_by_worker'] as bool? ?? false,
        createdAt: json['created_at'] as String? ?? '',
        urgent: json['urgent'] as bool? ?? false,
        recurrence: json['recurrence'] as String? ?? 'none',
      );
}
