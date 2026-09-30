import '../core/constants/api_constants.dart';
import '../core/network/api_client.dart';
import '../models/auth_session.dart';
import '../models/user_model.dart';

/// Service responsible for communicating with FastAPI authentication endpoints.
class AuthApiService {
  final ApiClient _apiClient;

  AuthApiService({ApiClient? apiClient}) : _apiClient = apiClient ?? ApiClient();

  /// Authenticate patient credentials against POST /api/auth/login.
  Future<AuthSession> login({
    required String email,
    required String password,
  }) async {
    final response = await _apiClient.post(
      ApiConstants.loginEndpoint,
      body: {
        'email': email.trim().toLowerCase(),
        'password': password,
      },
      includeAuth: false,
    );

    return AuthSession.fromJson(response as Map<String, dynamic>);
  }

  /// Fetch currently authenticated user profile via GET /api/auth/me.
  Future<UserModel> getCurrentUser() async {
    final response = await _apiClient.get(
      ApiConstants.meEndpoint,
      includeAuth: true,
    );

    return UserModel.fromJson(response as Map<String, dynamic>);
  }

  /// Revoke active session on backend via POST /api/auth/logout.
  Future<void> logout(String refreshToken) async {
    await _apiClient.post(
      ApiConstants.logoutEndpoint,
      body: {
        'refreshToken': refreshToken,
      },
      includeAuth: false,
    );
  }
}
