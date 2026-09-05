import '../models/bootstrap.dart';
import '../models/geo.dart';
import '../networking/api_client.dart';

/// GET /bootstrap + the standalone /geo/* endpoints (backend/routes/public.py)
/// — cascading state→city→neighborhood lookups used by signup and order
/// creation, same endpoints the RN app's signup.tsx already calls.
class BootstrapRepository {
  BootstrapRepository(this._client);
  final ApiClient _client;

  Future<Bootstrap> fetchBootstrap() async {
    final json = await _client.get<Map<String, dynamic>>('/bootstrap');
    return Bootstrap.fromJson(json);
  }

  Future<Map<String, bool>> fetchFeatureFlags() async {
    final json = await _client.get<Map<String, dynamic>>('/feature-flags');
    return json.map((k, v) => MapEntry(k, v as bool));
  }

  Future<List<StateRef>> fetchStates() async {
    final json = await _client.get<List<dynamic>>('/geo/states');
    return json.map((s) => StateRef.fromJson(s as Map<String, dynamic>)).toList();
  }

  Future<List<City>> fetchCities({String? stateId}) async {
    final json = await _client.get<List<dynamic>>(
      '/geo/cities',
      query: stateId != null ? {'state_id': stateId} : null,
    );
    return json.map((c) => City.fromJson(c as Map<String, dynamic>)).toList();
  }

  Future<List<Neighborhood>> fetchNeighborhoods({String? cityId}) async {
    final json = await _client.get<List<dynamic>>(
      '/geo/neighborhoods',
      query: cityId != null ? {'city_id': cityId} : null,
    );
    return json.map((n) => Neighborhood.fromJson(n as Map<String, dynamic>)).toList();
  }

  Future<List<Category>> fetchCategories() async {
    final json = await _client.get<List<dynamic>>('/categories');
    return json.map((c) => Category.fromJson(c as Map<String, dynamic>)).toList();
  }
}
