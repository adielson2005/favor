import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Session token storage — Keychain on iOS, EncryptedSharedPreferences on
/// Android. Same guarantee as the RN app's expo-secure-store, same key names
/// (frontend/src/auth.tsx: TOKEN_KEY = "faze:token") so both clients could in
/// principle share a device's stored session shape, even though they never
/// literally share storage.
class SecureStorage {
  SecureStorage._();
  static final SecureStorage instance = SecureStorage._();

  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  static const _userTokenKey = 'faze:token';
  static const _adminTokenKey = 'faze:admin_token';

  Future<String?> readUserToken() => _storage.read(key: _userTokenKey);
  Future<void> writeUserToken(String token) => _storage.write(key: _userTokenKey, value: token);
  Future<void> clearUserToken() => _storage.delete(key: _userTokenKey);

  Future<String?> readAdminToken() => _storage.read(key: _adminTokenKey);
  Future<void> writeAdminToken(String token) => _storage.write(key: _adminTokenKey, value: token);
  Future<void> clearAdminToken() => _storage.delete(key: _adminTokenKey);
}
