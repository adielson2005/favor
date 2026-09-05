/// Thrown for any non-2xx API response. Carries the backend's own `detail`
/// message (FastAPI's HTTPException shape: `{"detail": "..."}`) so UI can show
/// the exact same Portuguese error copy the backend already writes — mirrors
/// frontend/src/api.ts's `data?.detail || "Não conseguimos completar isso
/// agora. Tente novamente."` fallback exactly, so behavior doesn't diverge
/// between the two clients hitting the same backend.
class ApiException implements Exception {
  final int? statusCode;
  final String message;
  final dynamic body;

  const ApiException({required this.message, this.statusCode, this.body});

  static const _fallback = 'Não conseguimos completar isso agora. Tente novamente.';

  factory ApiException.fromResponse(int? statusCode, dynamic data) {
    final detail = (data is Map && data['detail'] is String) ? data['detail'] as String : null;
    return ApiException(statusCode: statusCode, message: detail ?? _fallback, body: data);
  }

  bool get isUnauthorized => statusCode == 401;
  bool get isForbidden => statusCode == 403;
  bool get isNotFound => statusCode == 404;
  bool get isRateLimited => statusCode == 429;

  @override
  String toString() => message;
}
