import 'package:http/http.dart' as http;

import '../core/constants/api_constants.dart';
import '../core/network/api_client.dart';
import '../core/network/api_exceptions.dart';
import '../models/auth_session.dart';
import '../models/doctor_application_status.dart';
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

  /// Authenticate patient with Google ID token against POST /api/auth/google.
  Future<AuthSession> authenticateWithGoogle({
    required String idToken,
  }) async {
    final response = await _apiClient.post(
      ApiConstants.googleAuthEndpoint,
      body: {
        'idToken': idToken,
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

  /// Request a password reset code against POST /api/auth/forgot-password.
  Future<String> forgotPassword({
    required String email,
  }) async {
    final response = await _apiClient.post(
      ApiConstants.forgotPasswordEndpoint,
      body: {
        'email': email.trim().toLowerCase(),
      },
      includeAuth: false,
    );

    if (response is Map<String, dynamic> && response['message'] != null) {
      return response['message'] as String;
    }
    return 'If an account exists for this email, a password reset code has been sent.';
  }

  /// Verify 6-digit reset OTP against POST /api/auth/verify-reset-otp and obtain resetToken.
  Future<String> verifyResetOtp({
    required String email,
    required String otp,
  }) async {
    final response = await _apiClient.post(
      ApiConstants.verifyResetOtpEndpoint,
      body: {
        'email': email.trim().toLowerCase(),
        'otp': otp.trim(),
      },
      includeAuth: false,
    );

    if (response is Map<String, dynamic> && response['resetToken'] != null) {
      return response['resetToken'] as String;
    }
    throw const ApiException(
      message: 'Invalid reset response received. Please try again.',
    );
  }

  /// Reset password against POST /api/auth/reset-password using verified resetToken.
  Future<String> resetPassword({
    required String resetToken,
    required String newPassword,
    required String confirmPassword,
  }) async {
    final response = await _apiClient.post(
      ApiConstants.resetPasswordEndpoint,
      body: {
        'resetToken': resetToken,
        'newPassword': newPassword,
        'confirmPassword': confirmPassword,
      },
      includeAuth: false,
    );

    if (response is Map<String, dynamic> && response['message'] != null) {
      return response['message'] as String;
    }
    return 'Password reset successfully. Please log in again.';
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

  /// Register a new doctor account with documents against POST /api/auth/register-doctor.
  Future<Map<String, dynamic>> registerDoctor({
    required String fullName,
    required String email,
    required String phone,
    required String password,
    required String specialty,
    required String medicalRegistrationNumber,
    required String qualifications,
    required String hospitalOrClinic,
    required int experienceYears,
    String? bio,
    required http.MultipartFile identityDocument,
    required http.MultipartFile medicalRegistrationDocument,
    required http.MultipartFile qualificationDocument,
  }) async {
    final fields = <String, String>{
      'fullName': fullName.trim(),
      'email': email.trim().toLowerCase(),
      'phone': phone.trim(),
      'password': password,
      'specialty': specialty.trim(),
      'medicalRegistrationNumber': medicalRegistrationNumber.trim(),
      'qualifications': qualifications.trim(),
      'hospitalOrClinic': hospitalOrClinic.trim(),
      'experienceYears': experienceYears.toString(),
    };
    if (bio != null && bio.trim().isNotEmpty) {
      fields['bio'] = bio.trim();
    }

    final response = await _apiClient.postMultipart(
      ApiConstants.registerDoctorEndpoint,
      fields: fields,
      files: [
        identityDocument,
        medicalRegistrationDocument,
        qualificationDocument,
      ],
      includeAuth: false,
    );

    return response as Map<String, dynamic>;
  }

  /// Fetch application status for authenticated doctor via GET /api/doctors/me/application-status.
  Future<DoctorApplicationStatus> getDoctorApplicationStatus() async {
    final response = await _apiClient.get(
      ApiConstants.doctorApplicationStatusEndpoint,
      includeAuth: true,
    );

    return DoctorApplicationStatus.fromJson(response as Map<String, dynamic>);
  }
}
