import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Secure token and session storage service for MediConnect.
/// Uses platform-level keychain / encrypted keystore via FlutterSecureStorage.
/// Never logs or prints sensitive token values.
class SecureStorageService {
  static const String _accessTokenKey = 'mediconnect_access_token';
  static const String _refreshTokenKey = 'mediconnect_refresh_token';
  static const String _userCacheKey = 'mediconnect_user_cache';
  static const String _serverUrlKey = 'mediconnect_server_url';

  final FlutterSecureStorage _storage;

  SecureStorageService({FlutterSecureStorage? storage})
      : _storage = storage ??
            const FlutterSecureStorage(
              aOptions: AndroidOptions(
                resetOnError: true,
              ),
              iOptions: IOSOptions(
                accessibility: KeychainAccessibility.first_unlock,
              ),
            );

  /// Retrieves the stored JWT access token, or null if absent.
  Future<String?> getAccessToken() async {
    try {
      return await _storage.read(key: _accessTokenKey);
    } catch (_) {
      return null;
    }
  }

  /// Retrieves the stored refresh token, or null if absent.
  Future<String?> getRefreshToken() async {
    try {
      return await _storage.read(key: _refreshTokenKey);
    } catch (_) {
      return null;
    }
  }

  /// Persists both access token and refresh token securely.
  Future<void> saveTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    await _storage.write(key: _accessTokenKey, value: accessToken);
    await _storage.write(key: _refreshTokenKey, value: refreshToken);
  }

  /// Persists cached user JSON representation for offline/quick access.
  Future<void> saveUserJson(String userJson) async {
    await _storage.write(key: _userCacheKey, value: userJson);
  }

  /// Retrieves cached user JSON representation.
  Future<String?> getUserJson() async {
    try {
      return await _storage.read(key: _userCacheKey);
    } catch (_) {
      return null;
    }
  }

  /// Persists a custom server URL.
  Future<void> saveServerUrl(String serverUrl) async {
    await _storage.write(key: _serverUrlKey, value: serverUrl);
  }

  /// Retrieves the stored server URL, or null if absent.
  Future<String?> getServerUrl() async {
    try {
      return await _storage.read(key: _serverUrlKey);
    } catch (_) {
      return null;
    }
  }

  /// Clears the stored server URL.
  Future<void> clearServerUrl() async {
    try {
      await _storage.delete(key: _serverUrlKey);
    } catch (_) {
      // Best-effort cleanup
    }
  }

  /// Clears stored access and refresh tokens.
  Future<void> clearTokens() async {
    try {
      await _storage.delete(key: _accessTokenKey);
      await _storage.delete(key: _refreshTokenKey);
    } catch (_) {
      // Best-effort cleanup
    }
  }

  /// Clears all stored auth session data.
  Future<void> clearAll() async {
    try {
      await _storage.delete(key: _accessTokenKey);
      await _storage.delete(key: _refreshTokenKey);
      await _storage.delete(key: _userCacheKey);
    } catch (_) {
      // Best-effort cleanup
    }
  }
}
