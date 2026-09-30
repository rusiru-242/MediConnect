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

  /// Register a new patient account against POST /api/auth/register.
  Future<Map<String, dynamic>> registerPatient({
    required String fullName,
    required String email,
    required String phone,
    required String password,
  }) async {
    final response = await _apiClient.post(
      ApiConstants.registerEndpoint,
      body: {
        'fullName': fullName.trim(),
        'email': email.trim().toLowerCase(),
        'phone': phone.trim(),
        'password': password,
      },
      includeAuth: false,
    );

    return response as Map<String, dynamic>;
  }

  /// Verify patient email address against POST /api/auth/verify-email.
  Future<String> verifyEmail({
    required String email,
    required String otp,
  }) async {
    final response = await _apiClient.post(
      ApiConstants.verifyEmailEndpoint,
      body: {
        'email': email.trim().toLowerCase(),
        'otp': otp.trim(),
      },
      includeAuth: false,
    );

    if (response is Map<String, dynamic> && response['message'] != null) {
      return response['message'] as String;
    }
    return 'Email verified successfully.';
  }

  /// Request a new 6-digit OTP code against POST /api/auth/resend-verification.
  Future<String> resendVerificationOtp({
    required String email,
  }) async {
    final response = await _apiClient.post(
      ApiConstants.resendVerificationEndpoint,
      body: {
        'email': email.trim().toLowerCase(),
      },
      includeAuth: false,
    );

    if (response is Map<String, dynamic> && response['message'] != null) {
      return response['message'] as String;
    }
    return 'Verification code has been resent successfully.';
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
