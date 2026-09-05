import 'geo.dart';
import 'user.dart';

/// Shape of GET /bootstrap (backend/routes/public.py:142) — the one call that
/// primes the whole app on cold start: demo users (dev-only), full geo
/// hierarchy, catalog, and feature flags. Mirrors what frontend/src/state.tsx
/// fans out to every screen via context; here it's just a typed holder any
/// repository/provider can read from.
class Bootstrap {
  final List<AppUser> demoUsers;
  final List<StateRef> states;
  final List<City> cities;
  final List<Neighborhood> neighborhoods;
  final List<Category> categories;
  final Map<String, bool> featureFlags;

  const Bootstrap({
    required this.demoUsers,
    required this.states,
    required this.cities,
    required this.neighborhoods,
    required this.categories,
    required this.featureFlags,
  });

  factory Bootstrap.fromJson(Map<String, dynamic> json) => Bootstrap(
        demoUsers: (json['users'] as List<dynamic>? ?? [])
            .map((u) => AppUser.fromJson(u as Map<String, dynamic>))
            .toList(),
        states: (json['states'] as List<dynamic>? ?? [])
            .map((s) => StateRef.fromJson(s as Map<String, dynamic>))
            .toList(),
        cities: (json['cities'] as List<dynamic>? ?? [])
            .map((c) => City.fromJson(c as Map<String, dynamic>))
            .toList(),
        neighborhoods: (json['neighborhoods'] as List<dynamic>? ?? [])
            .map((n) => Neighborhood.fromJson(n as Map<String, dynamic>))
            .toList(),
        categories: (json['categories'] as List<dynamic>? ?? [])
            .map((c) => Category.fromJson(c as Map<String, dynamic>))
            .toList(),
        featureFlags: (json['feature_flags'] as Map<String, dynamic>? ?? {})
            .map((k, v) => MapEntry(k, v as bool)),
      );

  bool flag(String key) => featureFlags[key] ?? false;
}
