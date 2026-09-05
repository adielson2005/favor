import '../models/proposal.dart';
import '../networking/api_client.dart';

/// Mirrors backend/routes/public.py's proposals endpoints. `fetchForOrder`
/// naturally returns either every proposal (if the caller owns the order) or
/// just the caller's own single proposal (if they're a worker) — the backend
/// enforces that scoping, this just calls the one endpoint either way.
class ProposalsRepository {
  ProposalsRepository(this._client);
  final ApiClient _client;

  Future<List<Proposal>> fetchForOrder(String orderId) async {
    final json = await _client.get<List<dynamic>>('/orders/$orderId/proposals');
    return json.map((p) => Proposal.fromJson(p as Map<String, dynamic>)).toList();
  }

  Future<Proposal> create({
    required String orderId,
    required double amount,
    String message = '',
    String eta = '',
  }) async {
    final json = await _client.post<Map<String, dynamic>>('/orders/$orderId/proposals', body: {
      'amount': amount,
      'message': message,
      'eta': eta,
    });
    return Proposal.fromJson(json);
  }

  Future<void> accept(String proposalId) => _client.post('/proposals/$proposalId/accept');

  Future<void> cancel(String proposalId) => _client.post('/proposals/$proposalId/cancel');
}
