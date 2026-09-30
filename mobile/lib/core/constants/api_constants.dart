import 'dart:io' show Platform;
import 'package:flutter/foundation.dart' show kIsWeb;

/// Centralized API configuration for MediConnect.
class ApiConstants {
  ApiConstants._();

  /// Default API base URL depending on platform.
  /// Android emulator uses 10.0.2.2 to access host machine localhost.
  /// iOS simulator, desktop, and other platforms use 127.0.0.1.
  static String get defaultBaseUrl {
    if (kIsWeb) {
      return 'http://127.0.0.1:8000/api';
    }
    try {
      if (Platform.isAndroid) {
        return 'http://10.0.2.2:8000/api';
      }
    } catch (_) {
      // Platform check may fail in unsupported environments, fallback to localhost
    }
    return 'http://127.0.0.1:8000/api';
  }

  /// Active base URL. Can be modified at runtime if needed.
  static String baseUrl = defaultBaseUrl;

  // Request timeout duration
  static const Duration timeoutDuration = Duration(seconds: 15);

  // Authentication endpoints
  static const String loginEndpoint = '/auth/login';
  static const String registerEndpoint = '/auth/register';
  static const String verifyEmailEndpoint = '/auth/verify-email';
  static const String resendVerificationEndpoint = '/auth/resend-verification';
  static const String forgotPasswordEndpoint = '/auth/forgot-password';
  static const String verifyResetOtpEndpoint = '/auth/verify-reset-otp';
  static const String resetPasswordEndpoint = '/auth/reset-password';
  static const String refreshEndpoint = '/auth/refresh';
  static const String logoutEndpoint = '/auth/logout';
  static const String meEndpoint = '/auth/me';
  static const String googleAuthEndpoint = '/auth/google';
  static const String registerDoctorEndpoint = '/auth/register-doctor';

  // Doctor endpoints
  static const String doctorApplicationStatusEndpoint = '/doctors/me/application-status';

  // Admin endpoints
  static const String adminDoctorApplicationsEndpoint = '/admin/doctors/applications';
  static String adminDoctorApplicationDetailEndpoint(String id) => '/admin/doctors/applications/$id';
  static String adminDoctorDocumentEndpoint(String id, String docKey) =>
      '/admin/doctors/applications/$id/documents/$docKey';
  static String adminDoctorApproveEndpoint(String id) => '/admin/doctors/$id/approve';
  static String adminDoctorRejectEndpoint(String id) => '/admin/doctors/$id/reject';

  /// Google OAuth Web Client ID (audience for ID tokens verified by backend).
  static const String googleServerClientId =
      '80346479357-pe3nov35fcpamn13q49llh4hc4amc1lj.apps.googleusercontent.com';
}
