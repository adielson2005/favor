/// Which backend this build talks to. Mirrors the existing React Native app's
/// single EXPO_PUBLIC_BACKEND_URL env var (frontend/src/api.ts) — same backend,
/// same /api prefix, same JWT bearer auth. No environment enum existed there
/// either; this adds one since Flutter builds need it split by --dart-define
/// per build (debug/profile/release don't share a runtime .env file the way
/// Metro does).
enum AppEnv { development, staging, production }

class AppEnvironment {
  const AppEnvironment._();

  /// Set via `--dart-define=API_BASE_URL=...`. Defaults to the same local
  /// backend the RN app's frontend/.env points at during development.
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );

  static const String envName = String.fromEnvironment(
    'APP_ENV',
    defaultValue: 'development',
  );

  /// The *Web application* OAuth client ID from Google Cloud Console — same
  /// value as the backend's GOOGLE_CLIENT_ID env var (routes/auth.py verifies
  /// the ID token against this exact audience). Passed as `serverClientId` to
  /// GoogleSignIn.initialize(); required on Android since this app has no
  /// google-services.json. Empty by default — google_auth_service.dart treats
  /// that as "not configured" the same way the backend does.
  static const String googleServerClientId = String.fromEnvironment('GOOGLE_SERVER_CLIENT_ID');

  static AppEnv get current => switch (envName) {
        'production' => AppEnv.production,
        'staging' => AppEnv.staging,
        _ => AppEnv.development,
      };

  static bool get isProduction => current == AppEnv.production;

  /// Same shape as the backend: every real endpoint lives under /api.
  static String get apiUrl => '$apiBaseUrl/api';
}
