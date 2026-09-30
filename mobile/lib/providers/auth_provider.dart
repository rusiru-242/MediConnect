import 'dart:convert';
import 'package:flutter/foundation.dart';

import '../core/network/api_client.dart';
import '../core/network/api_exceptions.dart';
import '../core/storage/secure_storage_service.dart';
import '../models/user_model.dart';
import '../services/auth_api_service.dart';

enum AuthStatus {
  initial,
  checking,
  authenticated,
  unauthenticated,
}

/// Authentication state provider managing user session, login, logout, and token recovery.
class AuthProvider extends ChangeNotifier {
  final AuthApiService _authApiService;
  final SecureStorageService _storageService;

  AuthStatus _status = AuthStatus.initial;
  UserModel? _user;
  bool _isLoading = false;
  String? _errorMessage;

  AuthProvider({
    AuthApiService? authApiService,
    SecureStorageService? storageService,
  })  : _storageService = storageService ?? SecureStorageService(),
        _authApiService =
            authApiService ?? AuthApiService(apiClient: ApiClient(storageService: storageService));

  AuthStatus get status => _status;
  UserModel? get user => _user;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  bool get isAuthenticated => _status == AuthStatus.authenticated;

  /// Clear any active error message.
  void clearError() {
    if (_errorMessage != null) {
      _errorMessage = null;
      notifyListeners();
    }
  }

  /// Verifies active session on application startup via GET /api/auth/me.
  /// Never relies solely on the presence of a token.
  Future<void> checkAuthSession() async {
    _status = AuthStatus.checking;
    _errorMessage = null;
    notifyListeners();

    try {
      final accessToken = await _storageService.getAccessToken();

      if (accessToken == null || accessToken.isEmpty) {
        _status = AuthStatus.unauthenticated;
        _user = null;
        notifyListeners();
        return;
      }

      // Token exists, verify with backend GET /api/auth/me
      // Note: ApiClient handles automatic refresh rotation on 401 if refresh token is available
      final user = await _authApiService.getCurrentUser();
      _user = user;
      _status = AuthStatus.authenticated;
      await _storageService.saveUserJson(jsonEncode(user.toJson()));
      notifyListeners();
    } on AuthException {
      // Token is invalid/expired and refresh failed
      await _storageService.clearAll();
      _user = null;
      _status = AuthStatus.unauthenticated;
      notifyListeners();
    } on NetworkException {
      // If offline, check if we have a valid cached user profile
      final cachedJson = await _storageService.getUserJson();
      if (cachedJson != null) {
        try {
          final decoded = jsonDecode(cachedJson) as Map<String, dynamic>;
          _user = UserModel.fromJson(decoded);
          _status = AuthStatus.authenticated;
          notifyListeners();
          return;
        } catch (_) {}
      }
      // Cannot verify and no cache available
      _user = null;
      _status = AuthStatus.unauthenticated;
      notifyListeners();
    } catch (_) {
      await _storageService.clearAll();
      _user = null;
      _status = AuthStatus.unauthenticated;
      notifyListeners();
    }
  }

  /// Authenticate patient credentials with POST /api/auth/login.
  Future<bool> login({
    required String email,
    required String password,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final session = await _authApiService.login(
        email: email,
        password: password,
      );

      // Store tokens securely
      await _storageService.saveTokens(
        accessToken: session.accessToken,
        refreshToken: session.refreshToken,
      );

      // Cache user profile
      await _storageService.saveUserJson(jsonEncode(session.user.toJson()));

      _user = session.user;
      _status = AuthStatus.authenticated;
      _isLoading = false;
      notifyListeners();
      return true;
    } on ApiException catch (e) {
      _errorMessage = e.message;
      _isLoading = false;
      notifyListeners();
      return false;
    } catch (e) {
      _errorMessage = 'An unexpected error occurred. Please try again.';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Log out patient, revoking session on backend and clearing secure storage.
  Future<void> logout() async {
    _isLoading = true;
    notifyListeners();

    try {
      final refreshToken = await _storageService.getRefreshToken();
      if (refreshToken != null && refreshToken.isNotEmpty) {
        try {
          await _authApiService.logout(refreshToken);
        } catch (_) {
          // Safe local session cleanup even if network request fails
        }
      }
    } finally {
      await _storageService.clearAll();
      _user = null;
      _status = AuthStatus.unauthenticated;
      _isLoading = false;
      _errorMessage = null;
      notifyListeners();
    }
  }
}
