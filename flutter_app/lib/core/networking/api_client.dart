import 'dart:async';

import 'package:dio/dio.dart';

import '../config/app_environment.dart';
import '../errors/api_exception.dart';

/// Thin REST client over the existing FastAPI backend — mirrors
/// frontend/src/api.ts's `request()` helper exactly:
///   - every path is relative to /api
///   - `Authorization: Bearer <token>` attached when a token is set
///   - non-2xx responses are unwrapped into ApiException using the
///     backend's {"detail": "..."} shape
///   - idempotency-key generation for financial POSTs (deposits, withdrawals,
///     payments, admin wallet adjustments) — the backend dedupes on this key
///     (backend/routes/wallet.py), so a retried tap or flaky connection can't
///     turn one payment into two.
///
/// Also mirrors a specific, non-obvious fix from the RN app: screens can fire
/// their data-fetching calls before the stored token has been read back from
/// secure storage on cold start. The RN app fixes this with an
/// `authReadyPromise` every request awaits before firing (frontend/src/api.ts).
/// `ApiClient` reproduces the same gate via [markAuthReady] / an internal
/// completer, so a fresh launch can never silently send an unauthenticated
/// request that should have had a token.
class ApiClient {
  ApiClient._internal() : _dio = Dio(BaseOptions(baseUrl: AppEnvironment.apiUrl)) {
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        await authReady;
        if (_token != null) {
          options.headers['Authorization'] = 'Bearer $_token';
        }
        handler.next(options);
      },
      onError: (DioException e, handler) {
        handler.next(_toDioExceptionWithApiError(e));
      },
    ));
  }

  static final ApiClient instance = ApiClient._internal();

  final Dio _dio;
  String? _token;

  final Completer<void> _authReadyCompleter = Completer<void>();
  Future<void> get authReady => _authReadyCompleter.future;

  /// Called once by the auth bootstrap after reading (or failing to find) a
  /// stored token — see features/auth/auth_controller.dart. Never call this
  /// more than once; a second call is a no-op via Completer's own guard.
  void markAuthReady() {
    if (!_authReadyCompleter.isCompleted) _authReadyCompleter.complete();
  }

  void setToken(String? token) => _token = token;

  DioException _toDioExceptionWithApiError(DioException e) {
    final apiError = ApiException.fromResponse(e.response?.statusCode, e.response?.data);
    return e.copyWith(error: apiError);
  }

  Future<T> _unwrap<T>(Future<Response<dynamic>> Function() call) async {
    try {
      final res = await call();
      return res.data as T;
    } on DioException catch (e) {
      if (e.error is ApiException) throw e.error as ApiException;
      throw ApiException(message: e.message ?? 'Falha de conexão. Verifique sua internet.');
    }
  }

  Future<T> get<T>(String path, {Map<String, dynamic>? query}) =>
      _unwrap<T>(() => _dio.get(path, queryParameters: query));

  Future<T> post<T>(String path, {Object? body, Map<String, String>? headers}) =>
      _unwrap<T>(() => _dio.post(path, data: body, options: Options(headers: headers)));

  Future<T> patch<T>(String path, {Object? body}) => _unwrap<T>(() => _dio.patch(path, data: body));

  Future<T> delete<T>(String path, {Object? body}) =>
      _unwrap<T>(() => _dio.delete(path, data: body));
}

/// A fresh key per financial action — see class doc above. Same shape as the
/// RN app's `idem-${Date.now()}-${Math.random()...}` (frontend/src/api.ts) so
/// backend logs/debugging aren't confused by two different formats.
String newIdempotencyKey() {
  final rand = (DateTime.now().microsecondsSinceEpoch % 0x7fffffff).toRadixString(36);
  return 'idem-${DateTime.now().millisecondsSinceEpoch}-$rand';
}
