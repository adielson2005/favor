// Proves FASE 14 (Testes) coverage of a real, previously-untested gap:
// GET /bootstrap is the single call every screen's geo/category/feature-flag
// data ultimately comes from (via bootstrapProvider), but no test ever
// exercised Bootstrap.fromJson against the real backend response — every
// other live test just passes hardcoded IDs (city-parauapebas, nb-1) without
// ever confirming those IDs actually come back from a real /bootstrap call.
//
//   flutter test test/bootstrap_repository_live_test.dart --dart-define=API_BASE_URL=http://localhost:8000
import 'package:flutter_test/flutter_test.dart';

import 'package:fazum/core/networking/api_client.dart';
import 'package:fazum/core/repositories/bootstrap_repository.dart';

void main() {
  ApiClient.instance.markAuthReady();

  test('fetchBootstrap returns real Parauapebas geo data and parses cleanly', () async {
    final repo = BootstrapRepository(ApiClient.instance);
    final bootstrap = await repo.fetchBootstrap();

    expect(bootstrap.cities.any((c) => c.id == 'city-parauapebas'), isTrue);
    expect(bootstrap.neighborhoods.any((n) => n.id == 'nb-1'), isTrue);
    // Every neighborhood must belong to a real city in the same response —
    // never a dangling/invented reference.
    final cityIds = bootstrap.cities.map((c) => c.id).toSet();
    for (final hood in bootstrap.neighborhoods) {
      expect(cityIds.contains(hood.cityId), isTrue, reason: 'neighborhood ${hood.id} references unknown city ${hood.cityId}');
    }
    expect(bootstrap.states, isNotEmpty);
    expect(bootstrap.categories, isNotEmpty);
    expect(bootstrap.featureFlags, isA<Map<String, bool>>());
  });

  test('fetchCategories, fetchStates, fetchCities and fetchNeighborhoods (used directly by signup) all resolve', () async {
    final repo = BootstrapRepository(ApiClient.instance);

    final categories = await repo.fetchCategories();
    expect(categories, isNotEmpty);

    final states = await repo.fetchStates();
    expect(states, isNotEmpty);
    final stateId = states.first.id;

    final cities = await repo.fetchCities(stateId: stateId);
    expect(cities, isNotEmpty);
    expect(cities.any((c) => c.id == 'city-parauapebas'), isTrue);

    final hoods = await repo.fetchNeighborhoods(cityId: 'city-parauapebas');
    expect(hoods, isNotEmpty);
    expect(hoods.any((n) => n.id == 'nb-1'), isTrue);
  });
}
