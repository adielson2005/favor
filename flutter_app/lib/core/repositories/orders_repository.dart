import '../models/order.dart';
import '../networking/api_client.dart';

/// Mirrors GET /orders' query params exactly (backend/routes/public.py) —
/// client_id/worker_id are always the CALLER's own id server-side regardless
/// of what's sent (an IDOR fix from an earlier audit), so passing `true` here
/// just means "filter to mine," not an arbitrary user id.
class OrdersRepository {
  OrdersRepository(this._client);
  final ApiClient _client;

  Future<List<Order>> fetchOrders({
    String? cityId,
    String? categoryId,
    String? neighborhoodId,
    String? type,
    String? q,
    String? status,
    bool mine = false,
    bool asWorker = false,
    double? maxBudget,
    bool? urgent,
    int limit = 20,
    int offset = 0,
  }) async {
    final query = <String, dynamic>{'limit': limit, 'offset': offset};
    if (cityId != null) query['city_id'] = cityId;
    if (categoryId != null) query['category_id'] = categoryId;
    if (neighborhoodId != null) query['neighborhood_id'] = neighborhoodId;
    if (type != null) query['type'] = type;
    if (q != null) query['q'] = q;
    if (status != null) query['status'] = status;
    if (mine) query['client_id'] = 'me'; // value ignored server-side, presence = "mine"
    if (asWorker) query['worker_id'] = 'me';
    if (maxBudget != null) query['max_budget'] = maxBudget;
    if (urgent != null) query['urgent'] = urgent;

    final json = await _client.get<List<dynamic>>('/orders', query: query);
    return json.map((o) => Order.fromJson(o as Map<String, dynamic>)).toList();
  }

  Future<Order> fetchOrder(String orderId) async {
    final json = await _client.get<Map<String, dynamic>>('/orders/$orderId');
    return Order.fromJson(json);
  }

  /// Mirrors POST /orders' body exactly (backend/models.py's OrderCreate) —
  /// same field set frontend/app/create.tsx sends. `photos` are
  /// `data:image/jpeg;base64,...` data URIs, same shape the backend expects.
  Future<Order> createOrder({
    required String title,
    String description = '',
    required String type,
    required String categoryId,
    String? subcategoryId,
    required String cityId,
    String? neighborhoodId,
    String dateLabel = 'Hoje',
    String timeLabel = '',
    required double budget,
    List<String> photos = const [],
    Map<String, String> fields = const {},
    bool urgent = false,
    String recurrence = 'none',
  }) async {
    final json = await _client.post<Map<String, dynamic>>('/orders', body: {
      'title': title,
      'description': description,
      'type': type,
      'category_id': categoryId,
      'subcategory_id': subcategoryId,
      'city_id': cityId,
      'neighborhood_id': neighborhoodId,
      'date_label': dateLabel,
      'time_label': timeLabel,
      'budget': budget,
      'photos': photos,
      'fields': fields,
      'urgent': urgent,
      'recurrence': recurrence,
    });
    return Order.fromJson(json);
  }

  // ---------- lifecycle (FASE 8) ----------
  // Mirrors backend/routes/public.py's state machine exactly:
  //   published → accepted → in_progress → completion_requested → completed
  //   (published/accepted) → cancelled
  // Every transition is an atomic conditional update server-side (guarded by
  // current status), so a double-tap or stale client state just gets a 400
  // ("não está mais...") instead of corrupting the order — these calls don't
  // need to re-check status client-side before firing.

  /// Worker only, accepted → in_progress.
  Future<void> start(String orderId) => _client.post('/orders/$orderId/start');

  /// Worker only, in_progress → completion_requested (client still has the
  /// final say via [complete]).
  Future<void> requestCompletion(String orderId) =>
      _client.post('/orders/$orderId/request-completion');

  /// Client only, in_progress|completion_requested → completed. Releases any
  /// held payment server-side if one exists — payment isn't wired into this
  /// Flutter app yet (FASE 10), so today that block is always a no-op here.
  Future<void> complete(String orderId) => _client.post('/orders/$orderId/complete');

  /// Client only, published|accepted → cancelled. Refunds any held payment
  /// server-side if one exists (same FASE 10 caveat as [complete]).
  Future<void> cancel(String orderId) => _client.post('/orders/$orderId/cancel');
}
